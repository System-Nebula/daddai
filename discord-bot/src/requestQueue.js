/**
 * Priority queue for requests with deduplication.
 * Prevents duplicate concurrent requests and prioritizes important requests.
 */
const EventEmitter = require('events');
const crypto = require('crypto');
const logger = require('./logger');

// Request priorities
const PRIORITY = {
    CRITICAL: 0,    // Critical system operations
    HIGH: 1,        // User messages, admin commands
    NORMAL: 2,      // Regular requests
    LOW: 3          // Background tasks, cleanup
};

class RequestQueue extends EventEmitter {
    constructor(options = {}) {
        super();
        
        this.maxConcurrent = options.maxConcurrent || 10;
        this.deduplicationWindow = options.deduplicationWindow || 5000; // 5 seconds
        this.maxQueueSize = options.maxQueueSize || 1000;
        
        // Active requests: { requestId: { promise, resolve, reject, ... } }
        this.activeRequests = new Map();
        
        // Pending queue: Array of { priority, requestId, request, ... }
        this.queue = [];
        
        // Deduplication: { key: { requestId, timestamp, promise } }
        this.pendingDeduplication = new Map();
        
        // Statistics
        this.stats = {
            totalQueued: 0,
            totalProcessed: 0,
            totalDeduplicated: 0,
            totalRejected: 0,
            currentQueueSize: 0,
            currentActiveRequests: 0
        };
        
        // Start processing queue
        this._processQueue();
        
        // Cleanup deduplication map periodically
        this._cleanupInterval = setInterval(() => {
            this._cleanupDeduplication();
        }, this.deduplicationWindow);
    }
    
    /**
     * Generate request key for deduplication
     * @param {Object} request - Request object
     * @returns {string} Request key
     */
    _generateRequestKey(request) {
        const keyData = {
            service: request.service,
            method: request.method,
            params: request.params
        };
        const keyString = JSON.stringify(keyData);
        return crypto.createHash('sha256').update(keyString).digest('hex');
    }
    
    /**
     * Add request to queue
     * @param {Function} requestFn - Async function to execute
     * @param {Object} options - Request options
     * @param {number} options.priority - Request priority (default: NORMAL)
     * @param {string} options.service - Service name for logging
     * @param {string} options.method - Method name for logging
     * @param {boolean} options.deduplicate - Whether to deduplicate (default: true)
     * @param {Object} options.context - Context for logging
     * @returns {Promise<any>} Request result
     */
    async enqueue(requestFn, options = {}) {
        const {
            priority = PRIORITY.NORMAL,
            service = 'unknown',
            method = 'unknown',
            deduplicate = true,
            context = {}
        } = options;
        
        // Check queue size
        if (this.queue.length >= this.maxQueueSize) {
            this.stats.totalRejected++;
            logger.warn('[RequestQueue] Queue full, rejecting request', {
                service,
                method,
                queueSize: this.queue.length,
                ...context
            });
            throw new Error('Request queue is full');
        }
        
        const requestId = crypto.randomUUID ? crypto.randomUUID() : crypto.randomBytes(16).toString('hex');
        
        // Check for duplicate requests if deduplication enabled
        if (deduplicate) {
            const requestKey = this._generateRequestKey({ service, method, params: options.params });
            const existing = this.pendingDeduplication.get(requestKey);
            
            if (existing && (Date.now() - existing.timestamp) < this.deduplicationWindow) {
                // Return existing promise
                this.stats.totalDeduplicated++;
                logger.debug('[RequestQueue] Deduplicating request', {
                    requestId,
                    existingRequestId: existing.requestId,
                    service,
                    method,
                    ...context
                });
                return existing.promise;
            }
        }
        
        // Create promise for this request
        let resolve, reject;
        const promise = new Promise((res, rej) => {
            resolve = res;
            reject = rej;
        });
        
        // Store in deduplication map if enabled
        if (deduplicate) {
            const requestKey = this._generateRequestKey({ service, method, params: options.params });
            this.pendingDeduplication.set(requestKey, {
                requestId,
                timestamp: Date.now(),
                promise
            });
        }
        
        // Add to queue
        const queueItem = {
            requestId,
            requestFn,
            priority,
            service,
            method,
            context,
            resolve,
            reject,
            timestamp: Date.now()
        };
        
        this.queue.push(queueItem);
        this.stats.totalQueued++;
        this.stats.currentQueueSize = this.queue.length;
        
        // Sort queue by priority (lower number = higher priority)
        this.queue.sort((a, b) => a.priority - b.priority);
        
        logger.debug('[RequestQueue] Request queued', {
            requestId,
            service,
            method,
            priority,
            queuePosition: this.queue.indexOf(queueItem),
            ...context
        });
        
        // Process queue
        this._processQueue();
        
        return promise;
    }
    
    /**
     * Process queue (called automatically)
     */
    async _processQueue() {
        // Don't process if at max concurrent or queue is empty
        if (this.activeRequests.size >= this.maxConcurrent || this.queue.length === 0) {
            return;
        }
        
        // Get next item from queue (already sorted by priority)
        const item = this.queue.shift();
        if (!item) return;
        
        this.stats.currentQueueSize = this.queue.length;
        this.stats.currentActiveRequests = this.activeRequests.size + 1;
        
        // Add to active requests
        this.activeRequests.set(item.requestId, item);
        
        logger.debug('[RequestQueue] Processing request', {
            requestId: item.requestId,
            service: item.service,
            method: item.method,
            activeRequests: this.activeRequests.size,
            queueSize: this.queue.length,
            ...item.context
        });
        
        // Execute request
        const startTime = Date.now();
        try {
            const result = await item.requestFn();
            const duration = Date.now() - startTime;
            
            this.stats.totalProcessed++;
            item.resolve(result);
            
            logger.debug('[RequestQueue] Request completed', {
                requestId: item.requestId,
                service: item.service,
                method: item.method,
                duration: `${duration}ms`,
                ...item.context
            });
            
            this.emit('completed', {
                requestId: item.requestId,
                service: item.service,
                method: item.method,
                duration,
                success: true
            });
        } catch (error) {
            const duration = Date.now() - startTime;
            
            this.stats.totalProcessed++;
            item.reject(error);
            
            logger.error('[RequestQueue] Request failed', {
                requestId: item.requestId,
                service: item.service,
                method: item.method,
                duration: `${duration}ms`,
                error: error.message,
                ...item.context
            });
            
            this.emit('failed', {
                requestId: item.requestId,
                service: item.service,
                method: item.method,
                duration,
                error
            });
        } finally {
            // Remove from active requests
            this.activeRequests.delete(item.requestId);
            this.stats.currentActiveRequests = this.activeRequests.size;
            
            // Continue processing queue
            setImmediate(() => this._processQueue());
        }
    }
    
    /**
     * Cleanup old deduplication entries
     */
    _cleanupDeduplication() {
        const now = Date.now();
        for (const [key, entry] of this.pendingDeduplication.entries()) {
            if (now - entry.timestamp > this.deduplicationWindow) {
                this.pendingDeduplication.delete(key);
            }
        }
    }
    
    /**
     * Get queue statistics
     */
    getStats() {
        return {
            ...this.stats,
            activeRequests: this.activeRequests.size,
            queueSize: this.queue.length,
            deduplicationSize: this.pendingDeduplication.size
        };
    }
    
    /**
     * Clear queue (for shutdown or reset)
     */
    clear() {
        // Reject all pending requests
        for (const item of this.queue) {
            item.reject(new Error('Queue cleared'));
        }
        this.queue = [];
        this.stats.currentQueueSize = 0;
        logger.info('[RequestQueue] Queue cleared');
    }
    
    /**
     * Shutdown queue gracefully
     */
    async shutdown() {
        if (this._cleanupInterval) {
            clearInterval(this._cleanupInterval);
        }
        
        // Wait for active requests to complete (with timeout)
        const maxWait = 30000; // 30 seconds
        const startWait = Date.now();
        
        while (this.activeRequests.size > 0 && (Date.now() - startWait) < maxWait) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        // Clear remaining queue
        this.clear();
        
        logger.info('[RequestQueue] Queue shutdown complete');
    }
}

// Create singleton instance
const requestQueue = new RequestQueue({
    maxConcurrent: parseInt(process.env.MAX_CONCURRENT_REQUESTS) || 10,
    deduplicationWindow: parseInt(process.env.DEDUPLICATION_WINDOW) || 5000,
    maxQueueSize: parseInt(process.env.MAX_QUEUE_SIZE) || 1000
});

module.exports = { RequestQueue, requestQueue, PRIORITY };

