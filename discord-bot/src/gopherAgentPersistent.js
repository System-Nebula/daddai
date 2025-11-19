
/**
 * Persistent GopherAgent Service that keeps Python server alive.
 * Much faster than spawning new processes for each request.
 */
const { spawn } = require('child_process');
const path = require('path');
const EventEmitter = require('events');
const logger = require('./logger');

class PersistentGopherAgentService extends EventEmitter {
    constructor() {
        super();
        this.pythonPath = process.env.PYTHON_PATH || 'python';
        this.serverScriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'gopher_agent_persistent_server.py');
        this.serverProcess = null;
        this.requestQueue = [];
        this.requestId = 0;
        this.pendingRequests = new Map();
        this.isReady = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this._starting = false; // Guard flag to prevent concurrent starts
        
        this.startServer();
    }
    
    startServer() {
        // CRITICAL: Prevent concurrent server starts
        if (this.serverProcess || this._starting) {
            logger.debug('[GopherAgent] Server already started or starting, skipping...');
            return; // Already started or starting
        }
        
        this._starting = true;
        
        logger.info('[GopherAgent] Starting persistent server...');
        
        this.serverProcess = spawn(this.pythonPath, [this.serverScriptPath], {
            stdio: ['pipe', 'pipe', 'pipe']
        });
        
        let startupOutput = '';
        
        // Handle stderr (debug output)
        this.serverProcess.stderr.on('data', (data) => {
            const output = data.toString();
            startupOutput += output;
            console.log(`[GopherAgent Server] ${output.trim()}`);
            
            // Check if server is ready
            if (output.includes('GopherAgent server ready!')) {
                this.isReady = true;
                this._starting = false; // Clear starting flag
                this.reconnectAttempts = 0;
                logger.info('[GopherAgent] Server ready! Processing queued requests...');
                this.processQueue();
            }
        });
        
        // Handle stdout (responses)
        let buffer = '';
        this.serverProcess.stdout.on('data', (data) => {
            buffer += data.toString();
            
            // Process complete JSON lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const response = JSON.parse(line);
                        this.handleResponse(response);
                    } catch (error) {
                        logger.error('[GopherAgent] Failed to parse response:', { line, error: error.message });
                    }
                }
            }
        });
        
        // Handle process exit
        this.serverProcess.on('exit', (code) => {
            logger.error(`[GopherAgent] Server process exited with code ${code}`);
            this.serverProcess = null;
            this.isReady = false;
            this._starting = false; // Clear starting flag
            
            // Attempt to reconnect
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                logger.warn(`[GopherAgent] Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
                setTimeout(() => this.startServer(), 2000);
            } else {
                logger.error('[GopherAgent] Max reconnection attempts reached. Server unavailable.');
            }
        });
        
        // Handle errors
        this.serverProcess.on('error', (error) => {
            logger.error('[GopherAgent] Server process error:', { error: error.message, stack: error.stack });
            this.isReady = false;
            this._starting = false; // Clear starting flag
        });
    }
    
    handleResponse(response) {
        const requestId = response.id;
        const pending = this.pendingRequests.get(requestId);
        
        if (pending) {
            this.pendingRequests.delete(requestId);
            
            if (response.error) {
                pending.reject(new Error(response.error));
            } else {
                pending.resolve(response.result);
            }
        }
    }
    
    processQueue() {
        while (this.requestQueue.length > 0 && this.isReady) {
            const request = this.requestQueue.shift();
            this.sendRequest(request);
        }
    }
    
    sendRequest(request) {
        if (!this.isReady || !this.serverProcess) {
            this.requestQueue.push(request);
            return;
        }
        
        const requestJson = JSON.stringify(request) + '\n';
        this.serverProcess.stdin.write(requestJson);
    }
    
    /**
     * Route message to appropriate handler
     * @param {string} message - User's message
     * @param {Object} context - Context object (has_attachments, is_mentioned, etc.)
     * @param {Object} intentResult - Optional pre-computed intent result
     * @returns {Promise<Object>} Routing result with handler, intent, etc.
     */
    async routeMessage(message, context = {}, intentResult = null) {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const request = {
                id: requestId,
                method: 'route_message',
                params: {
                    message: message,
                    context: context,
                    intent_result: intentResult
                }
            };
            
            // Store pending request
            this.pendingRequests.set(requestId, { resolve, reject });
            
            // Set timeout (10 seconds - balanced for LLM classification)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[GopherAgent] Request timeout', { requestId, method: 'route_message' });
                    reject(new Error('GopherAgent request timeout'));
                }
            }, 10000);
            
            // Override resolve/reject to clear timeout
            const originalResolve = resolve;
            const originalReject = reject;
            this.pendingRequests.set(requestId, {
                resolve: (result) => {
                    clearTimeout(timeout);
                    originalResolve(result);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    originalReject(error);
                }
            });
            
            // Send request
            this.sendRequest(request);
        });
    }
    
    /**
     * Classify message intent
     * @param {string} message - User's message
     * @param {Object} context - Context object
     * @param {boolean} useCache - Whether to use cache
     * @returns {Promise<Object>} Intent classification result
     */
    async classifyIntent(message, context = {}, useCache = true) {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const request = {
                id: requestId,
                method: 'classify_intent',
                params: {
                    message: message,
                    context: context,
                    use_cache: useCache
                }
            };
            
            // Store pending request
            this.pendingRequests.set(requestId, { resolve, reject });
            
            // Set timeout (15 seconds)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[GopherAgent] Request timeout', { requestId, method: 'classify_intent' });
                    reject(new Error('GopherAgent request timeout'));
                }
            }, 15000);
            
            // Override resolve/reject to clear timeout
            const originalResolve = resolve;
            const originalReject = reject;
            this.pendingRequests.set(requestId, {
                resolve: (result) => {
                    clearTimeout(timeout);
                    originalResolve(result);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    originalReject(error);
                }
            });
            
            // Send request
            this.sendRequest(request);
        });
    }
    
    /**
     * Get performance metrics
     * @returns {Promise<Object>} Metrics object
     */
    async getMetrics() {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const request = {
                id: requestId,
                method: 'get_metrics',
                params: {}
            };
            
            // Store pending request
            this.pendingRequests.set(requestId, { resolve, reject });
            
            // Set timeout (5 seconds)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    reject(new Error('GopherAgent metrics timeout'));
                }
            }, 5000);
            
            // Override resolve/reject to clear timeout
            const originalResolve = resolve;
            const originalReject = reject;
            this.pendingRequests.set(requestId, {
                resolve: (result) => {
                    clearTimeout(timeout);
                    originalResolve(result);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    originalReject(error);
                }
            });
            
            // Send request
            this.sendRequest(request);
        });
    }
}

// Export singleton instance
module.exports = new PersistentGopherAgentService();

