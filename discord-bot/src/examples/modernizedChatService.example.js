/**
 * EXAMPLE: Modernized Chat Service
 * 
 * This file demonstrates how to modernize existing services using:
 * - Native fetch API with AbortController
 * - Modern error handling
 * - Better async patterns
 * - Structured logging
 * 
 * This is a reference implementation showing best practices.
 * Compare with src/chatService.js to see the improvements.
 */

const EventEmitter = require('events');
const { spawn } = require('child_process');
const path = require('path');
const { postJSON, fetchJSON, HTTPError, TimeoutError, isRetryableError } = require('../utils/httpClient');
const { ServiceUnavailableError, asyncHandler } = require('../utils/errorHandler');
const logger = require('../logger');
const { retryWithBackoff } = require('../retryLogic');
const CircuitBreaker = require('../circuitBreaker');

class ModernizedChatService extends EventEmitter {
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
        this._starting = false;
        
        // Modern: Circuit breaker for HTTP requests
        this.circuitBreaker = new CircuitBreaker({
            failureThreshold: 5,
            resetTimeout: 60000
        });
        
        this.startServer();
    }
    
    startServer() {
        if (this.serverProcess || this._starting) {
            logger.debug('[Chat] Server already started or starting, skipping...');
            return;
        }
        
        this._starting = true;
        logger.info('[Chat] Starting persistent chat server...');
        
        this.serverProcess = spawn(this.pythonPath, [this.serverScriptPath], {
            stdio: ['pipe', 'pipe', 'pipe']
        });
        
        // Modern: Use AbortController for process management
        const abortController = new AbortController();
        const signal = abortController.signal;
        
        // Handle stderr (debug output)
        this.serverProcess.stderr.on('data', (data) => {
            const output = data.toString();
            console.log(`[Chat Server] ${output.trim()}`);
            
            if (this.useHttp) {
                if (output.includes('Chat HTTP server starting') || output.includes('Chat server ready!')) {
                    setTimeout(async () => {
                        try {
                            await this.checkHttpServer();
                            this.isReady = true;
                            this._starting = false;
                            this.reconnectAttempts = 0;
                            logger.info('[Chat] HTTP server ready! Processing queued requests...');
                            this.processQueue();
                        } catch (error) {
                            logger.error('[Chat] HTTP server check failed', { error: error.message });
                        }
                    }, 2000);
                }
            } else {
                if (output.includes('Chat server ready!')) {
                    this.isReady = true;
                    this._starting = false;
                    this.reconnectAttempts = 0;
                    logger.info('[Chat] Server ready! Processing queued requests...');
                    this.processQueue();
                }
            }
        });
        
        // Handle stdout (responses) - same as before but with better error handling
        let buffer = '';
        this.serverProcess.stdout.on('data', (data) => {
            buffer += data.toString();
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const response = JSON.parse(line);
                        this.handleResponse(response);
                    } catch (error) {
                        logger.error('[Chat] Failed to parse response', { 
                            line, 
                            error: error.message 
                        });
                    }
                }
            }
        });
        
        // Modern: Better error handling
        this.serverProcess.on('exit', (code) => {
            logger.error('[Chat] Server process exited', { code });
            this.serverProcess = null;
            this.isReady = false;
            this._starting = false;
            
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                logger.warn('[Chat] Attempting to reconnect', { 
                    attempt: this.reconnectAttempts,
                    maxAttempts: this.maxReconnectAttempts 
                });
                setTimeout(() => this.startServer(), 2000);
            } else {
                logger.error('[Chat] Max reconnection attempts reached');
                this.emit('error', new ServiceUnavailableError('chat-server'));
            }
        });
        
        this.serverProcess.on('error', (error) => {
            logger.error('[Chat] Server process error', { 
                error: error.message,
                stack: error.stack 
            });
            this.isReady = false;
            this._starting = false;
        });
    }
    
    /**
     * Modern: HTTP request using native fetch with circuit breaker
     */
    async _sendHttpRequest(request) {
        const method = request.method;
        const params = request.params || {};
        
        let endpoint = '';
        let body = null;
        
        // Map methods to HTTP endpoints
        switch (method) {
            case 'chat':
                endpoint = '/chat';
                body = {
                    message: params.message,
                    history: params.history || [],
                    temperature: params.temperature || 0.85,
                    max_tokens: params.max_tokens || 500,
                    stream: params.stream || false
                };
                break;
            case 'ping':
                endpoint = '/ping';
                break;
            default:
                this.handleResponse({
                    id: request.id,
                    error: `Unknown method: ${method}`,
                    result: null
                });
                return;
        }
        
        const url = `${this.httpBaseUrl}${endpoint}`;
        
        try {
            // Modern: Use circuit breaker for resilience
            const response = await this.circuitBreaker.execute(async () => {
                if (method === 'ping') {
                    return await fetchJSON(url, { timeout: 5000 });
                } else {
                    return await postJSON(url, body, { timeout: 100000 });
                }
            }, { method, endpoint });
            
            this.handleResponse({
                id: request.id,
                result: response,
                error: response.error || null
            });
        } catch (error) {
            // Modern: Better error handling with retry logic
            if (isRetryableError(error) && this.reconnectAttempts < this.maxReconnectAttempts) {
                logger.warn('[Chat] Retryable error, will retry', { 
                    error: error.message,
                    requestId: request.id 
                });
                
                // Queue for retry
                this.requestQueue.push(request);
                return;
            }
            
            logger.error('[Chat] HTTP request failed', { 
                error: error.message,
                requestId: request.id,
                endpoint 
            });
            
            this.handleResponse({
                id: request.id,
                error: error instanceof HTTPError 
                    ? `HTTP ${error.status}: ${error.message}`
                    : error.message,
                result: null
            });
        }
    }
    
    /**
     * Modern: Health check using native fetch
     */
    async checkHttpServer() {
        try {
            const response = await fetchJSON(`${this.httpBaseUrl}/ping`, { 
                timeout: 5000 
            });
            return response;
        } catch (error) {
            if (error instanceof TimeoutError) {
                throw new ServiceUnavailableError('chat-server', error);
            }
            throw error;
        }
    }
    
    handleResponse(response) {
        const requestId = response.id;
        const pendingRequest = this.pendingRequests.get(requestId);
        
        if (pendingRequest) {
            this.pendingRequests.delete(requestId);
            if (response.error) {
                pendingRequest.reject(new Error(response.error));
            } else {
                pendingRequest.resolve(response.result);
            }
        }
    }
    
    /**
     * Modern: Send request with better error handling
     */
    sendRequest(request) {
        return new Promise((resolve, reject) => {
            request.id = ++this.requestId;
            
            this.pendingRequests.set(request.id, { resolve, reject });
            
            if (!this.isReady) {
                this.requestQueue.push(request);
                return;
            }
            
            if (this.useHttp) {
                this._sendHttpRequest(request);
            } else {
                // stdin/stdout mode (unchanged)
                // ... existing implementation
            }
        });
    }
    
    processQueue() {
        while (this.requestQueue.length > 0 && this.isReady) {
            const request = this.requestQueue.shift();
            if (this.useHttp) {
                this._sendHttpRequest(request);
            } else {
                // stdin/stdout mode
                // ... existing implementation
            }
        }
    }
}

module.exports = ModernizedChatService;

