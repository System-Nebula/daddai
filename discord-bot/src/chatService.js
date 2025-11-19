/**
 * Persistent Chat Service that keeps Python server alive.
 * Much faster than spawning new processes for each request.
 * Supports both stdin/stdout and HTTP REST API modes.
 */
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');
const EventEmitter = require('events');
const logger = require('./logger');

class PersistentChatService extends EventEmitter {
    constructor() {
        super();
        this.useHttp = process.env.USE_CHAT_SERVER_HTTP === 'true';
        this.httpPort = process.env.CHAT_SERVER_PORT || 8767;
        this.httpBaseUrl = `http://localhost:${this.httpPort}`;
        
        this.pythonPath = process.env.PYTHON_PATH || 'python';
        this.serverScriptPath = this.useHttp
            ? path.join(__dirname, '..', '..', 'src', 'api', 'chat_server_http.py')
            : path.join(__dirname, '..', '..', 'src', 'api', 'chat_server.py');
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
            logger.debug('[Chat] Server already started or starting, skipping...');
            return; // Already started or starting
        }
        
        this._starting = true;
        
        logger.info('[Chat] Starting persistent chat server...');
        
        this.serverProcess = spawn(this.pythonPath, [this.serverScriptPath], {
            stdio: ['pipe', 'pipe', 'pipe']
        });
        
        let startupOutput = '';
        
        // Handle stderr (debug output)
        this.serverProcess.stderr.on('data', (data) => {
            const output = data.toString();
            startupOutput += output;
            console.log(`[Chat Server] ${output.trim()}`);
            
            // Check if server is ready
            if (this.useHttp) {
                // For HTTP mode, check for HTTP server startup message
                if (output.includes('Chat HTTP server starting') || output.includes('Chat server ready!')) {
                    // Wait a bit for HTTP server to fully start
                    setTimeout(() => {
                        this.checkHttpServer().then(() => {
                            this.isReady = true;
                            this._starting = false;
                            this.reconnectAttempts = 0;
                            logger.info('[Chat] HTTP server ready! Processing queued requests...');
                            this.processQueue();
                        }).catch(() => {
                            // Will retry on next check
                        });
                    }, 2000);
                }
            } else {
                // For stdin/stdout mode
                if (output.includes('Chat server ready!')) {
                    this.isReady = true;
                    this._starting = false; // Clear starting flag
                    this.reconnectAttempts = 0;
                    logger.info('[Chat] Server ready! Processing queued requests...');
                    this.processQueue();
                }
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
                        logger.error('[Chat] Failed to parse response:', { line, error: error.message });
                    }
                }
            }
        });
        
        // Handle process exit
        this.serverProcess.on('exit', (code) => {
            logger.error(`[Chat] Server process exited with code ${code}`);
            this.serverProcess = null;
            this.isReady = false;
            this._starting = false; // Clear starting flag
            
            // Attempt to reconnect
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                logger.warn(`[Chat] Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
                setTimeout(() => this.startServer(), 2000);
            } else {
                logger.error('[Chat] Max reconnection attempts reached. Server unavailable.');
            }
        });
        
        // Handle errors
        this.serverProcess.on('error', (error) => {
            logger.error('[Chat] Server process error:', { error: error.message, stack: error.stack });
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
            this._sendRequestInternal(request);
        }
    }
    
    async checkHttpServer() {
        return new Promise((resolve, reject) => {
            const req = http.get(`${this.httpBaseUrl}/health`, (res) => {
                if (res.statusCode === 200) {
                    resolve();
                } else {
                    reject(new Error(`HTTP server returned status ${res.statusCode}`));
                }
            });
            req.on('error', reject);
            req.setTimeout(5000, () => {
                req.destroy();
                reject(new Error('HTTP server health check timeout'));
            });
        });
    }
    
    _sendRequestInternal(request) {
        if (!this.isReady) {
            this.requestQueue.push(request);
            return;
        }
        
        if (this.useHttp) {
            // HTTP mode - send HTTP request
            this._sendHttpRequest(request);
        } else {
            // stdin/stdout mode
            if (!this.serverProcess) {
                this.requestQueue.push(request);
                return;
            }
            const requestJson = JSON.stringify(request) + '\n';
            this.serverProcess.stdin.write(requestJson);
        }
    }
    
    _sendHttpRequest(request) {
        const method = request.method;
        const params = request.params || {};
        
        let endpoint = '';
        let body = null;
        let httpMethod = 'POST';
        
        // Map methods to HTTP endpoints
        switch (method) {
            case 'chat':
                endpoint = '/chat';
                body = JSON.stringify({
                    message: params.message,
                    history: params.history || [],
                    temperature: params.temperature || 0.85,
                    max_tokens: params.max_tokens || 500,
                    stream: params.stream || false
                });
                httpMethod = 'POST';
                break;
            case 'ping':
                endpoint = '/ping';
                httpMethod = 'GET';
                break;
            default:
                this.handleResponse({
                    id: request.id,
                    error: `Unknown method: ${method}`,
                    result: null
                });
                return;
        }
        const options = {
            hostname: 'localhost',
            port: this.httpPort,
            path: endpoint,
            method: httpMethod,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        const req = http.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => {
                data += chunk;
            });
            res.on('end', () => {
                try {
                    const response = JSON.parse(data);
                    this.handleResponse({
                        id: request.id,
                        result: response,
                        error: response.error || null
                    });
                } catch (error) {
                    logger.error('[Chat] Failed to parse HTTP response:', { error: error.message, data });
                    this.handleResponse({
                        id: request.id,
                        error: `Failed to parse response: ${error.message}`,
                        result: null
                    });
                }
            });
        });
        
        req.on('error', (error) => {
            logger.error('[Chat] HTTP request error:', { error: error.message });
            this.handleResponse({
                id: request.id,
                error: `HTTP request failed: ${error.message}`,
                result: null
            });
        });
        
        req.setTimeout(100000, () => {
            req.destroy();
            this.handleResponse({
                id: request.id,
                error: 'HTTP request timeout',
                result: null
            });
        });
        
        if (body) {
            req.write(body);
        }
        req.end();
    }
    
    /**
     * Send a request to the chat server
     * @param {Object} request - Request object with method and params
     * @returns {Promise<Object>} Response from server
     */
    sendRequest(request) {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const fullRequest = {
                id: requestId,
                method: request.method,
                params: request.params || {}
            };
            
            // Store pending request
            this.pendingRequests.set(requestId, { resolve, reject });
            
            // Set timeout (100 seconds for chat requests - increased to match original timeout)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[Chat] Request timeout', { requestId, method: request.method });
                    reject(new Error('Chat request timeout'));
                }
            }, 100000);
            
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
            this._sendRequestInternal(fullRequest);
        });
    }
    
    /**
     * Simple chat without RAG - direct LLM call
     * @param {string} message - User's message
     * @param {Array} conversationHistory - Previous conversation messages
     * @returns {Promise<string>} Response from LLM
     */
    async chat(message, conversationHistory = []) {
        try {
            const result = await this.sendRequest({
                method: 'chat',
                params: {
                    message: message,
                    history: conversationHistory.slice(-5), // Last 5 messages
                    temperature: 0.85,
                    max_tokens: 500
                }
            });
            
            return result.answer || result.message || 'Sorry, I could not generate a response.';
        } catch (error) {
            logger.error('[Chat] Error in chat:', error);
            throw error;
        }
    }
    
    shutdown() {
        if (this.serverProcess) {
            logger.info('[Chat] Shutting down persistent server...');
            this.serverProcess.kill();
            this.serverProcess = null;
            this.isReady = false;
        }
    }
}

// Export singleton instance
module.exports = new PersistentChatService();
