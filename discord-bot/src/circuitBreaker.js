/**
 * Circuit Breaker pattern for Python service calls.
 * Prevents cascading failures by opening circuit after consecutive failures.
 * Auto-recovers after a cooldown period.
 */
const EventEmitter = require('events');
const logger = require('./logger');

class CircuitBreaker extends EventEmitter {
    /**
     * @param {Object} options - Configuration options
     * @param {number} options.failureThreshold - Number of failures before opening circuit (default: 5)
     * @param {number} options.resetTimeout - Time in ms before attempting to close circuit (default: 60000)
     * @param {number} options.monitoringWindow - Time window in ms for tracking failures (default: 60000)
     */
    constructor(options = {}) {
        super();
        
        this.failureThreshold = options.failureThreshold || 5;
        this.resetTimeout = options.resetTimeout || 60000; // 1 minute
        this.monitoringWindow = options.monitoringWindow || 60000; // 1 minute
        
        // Circuit states: 'CLOSED', 'OPEN', 'HALF_OPEN'
        this.state = 'CLOSED';
        
        // Failure tracking
        this.failures = [];
        this.successCount = 0;
        this.lastFailureTime = null;
        this.nextAttemptTime = null;
        
        // Statistics
        this.stats = {
            totalRequests: 0,
            totalFailures: 0,
            totalSuccesses: 0,
            circuitOpens: 0,
            circuitCloses: 0
        };
    }
    
    /**
     * Execute a function with circuit breaker protection
     * @param {Function} fn - Async function to execute
     * @param {Object} context - Optional context for logging
     * @returns {Promise<any>} Result of the function
     */
    async execute(fn, context = {}) {
        this.stats.totalRequests++;
        
        // Check if circuit should be opened
        if (this.state === 'OPEN') {
            const now = Date.now();
            if (now < this.nextAttemptTime) {
                const waitTime = Math.ceil((this.nextAttemptTime - now) / 1000);
                logger.warn('[CircuitBreaker] Circuit is OPEN, rejecting request', {
                    ...context,
                    waitTime: `${waitTime}s`,
                    state: this.state
                });
                throw new Error(`Circuit breaker is OPEN. Try again in ${waitTime} seconds.`);
            } else {
                // Transition to HALF_OPEN to test if service recovered
                this.state = 'HALF_OPEN';
                this.successCount = 0;
                logger.info('[CircuitBreaker] Circuit transitioning to HALF_OPEN', context);
            }
        }
        
        // Clean old failures outside monitoring window
        this._cleanOldFailures();
        
        try {
            const result = await fn();
            
            // Success - reset failure tracking
            this._onSuccess(context);
            this.stats.totalSuccesses++;
            
            return result;
        } catch (error) {
            // Failure - track it
            this._onFailure(context, error);
            this.stats.totalFailures++;
            
            throw error;
        }
    }
    
    /**
     * Handle successful execution
     */
    _onSuccess(context) {
        this.lastFailureTime = null;
        
        if (this.state === 'HALF_OPEN') {
            this.successCount++;
            // If we get enough successes in half-open, close the circuit
            if (this.successCount >= 2) {
                this._closeCircuit(context);
            }
        } else if (this.state === 'CLOSED') {
            // Reset failure count on success
            this.failures = [];
        }
    }
    
    /**
     * Handle failed execution
     */
    _onFailure(context, error) {
        const now = Date.now();
        this.lastFailureTime = now;
        this.failures.push(now);
        
        // Clean old failures
        this._cleanOldFailures();
        
        if (this.state === 'HALF_OPEN') {
            // If we fail in half-open, immediately open again
            this._openCircuit(context, error);
        } else if (this.state === 'CLOSED') {
            // Check if we've exceeded failure threshold
            if (this.failures.length >= this.failureThreshold) {
                this._openCircuit(context, error);
            }
        }
    }
    
    /**
     * Open the circuit
     */
    _openCircuit(context, error) {
        if (this.state !== 'OPEN') {
            this.state = 'OPEN';
            this.nextAttemptTime = Date.now() + this.resetTimeout;
            this.stats.circuitOpens++;
            
            logger.error('[CircuitBreaker] Circuit OPENED', {
                ...context,
                failureCount: this.failures.length,
                error: error.message,
                nextAttempt: new Date(this.nextAttemptTime).toISOString()
            });
            
            this.emit('open', { context, error, failureCount: this.failures.length });
        }
    }
    
    /**
     * Close the circuit
     */
    _closeCircuit(context) {
        if (this.state !== 'CLOSED') {
            this.state = 'CLOSED';
            this.failures = [];
            this.successCount = 0;
            this.nextAttemptTime = null;
            this.stats.circuitCloses++;
            
            logger.info('[CircuitBreaker] Circuit CLOSED', context);
            this.emit('close', { context });
        }
    }
    
    /**
     * Clean failures outside monitoring window
     */
    _cleanOldFailures() {
        const now = Date.now();
        const cutoff = now - this.monitoringWindow;
        this.failures = this.failures.filter(time => time > cutoff);
    }
    
    /**
     * Get current circuit state
     */
    getState() {
        return {
            state: this.state,
            failures: this.failures.length,
            failureThreshold: this.failureThreshold,
            nextAttemptTime: this.nextAttemptTime,
            stats: { ...this.stats }
        };
    }
    
    /**
     * Manually reset the circuit breaker
     */
    reset() {
        this.state = 'CLOSED';
        this.failures = [];
        this.successCount = 0;
        this.lastFailureTime = null;
        this.nextAttemptTime = null;
        logger.info('[CircuitBreaker] Circuit manually reset');
    }
    
    /**
     * Manually open the circuit (for testing or manual intervention)
     */
    open() {
        this._openCircuit({ manual: true }, new Error('Manually opened'));
    }
}

/**
 * Create a circuit breaker instance with default settings
 */
function createCircuitBreaker(options = {}) {
    return new CircuitBreaker(options);
}

module.exports = { CircuitBreaker, createCircuitBreaker };

