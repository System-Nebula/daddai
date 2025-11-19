/**
 * Persistent Chat Service that keeps Python server alive.
 * Much faster than spawning new processes for each request.
 * Supports both stdin/stdout and HTTP REST API modes.
 */
import { spawn, ChildProcess } from 'child_process';
import * as http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';
import { EventEmitter } from 'events';
import logger from './logger';
import type { ChatRequest, ChatResponse } from './types';

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface PendingRequest {
    resolve: (result: unknown) => void;
    reject: (error: Error) => void;
}

interface ChatRequestParams {
    message: string;
    history?: Array<{ role: string; content: string }>;
    temperature?: number;
    max_tokens?: number;
    stream?: boolean;
    [key: string]: unknown;
}

interface InternalRequest {
    id: number;
    method: string;
    params: ChatRequestParams;
}

class PersistentChatService extends EventEmitter {
    private useHttp: boolean;
    private httpPort: number;
    private httpBaseUrl: string;
    private pythonPath: string;
    private serverScriptPath: string;
    private serverProcess: ChildProcess | null = null;
    private requestQueue: InternalRequest[] = [];
    private requestId = 0;
    private pendingRequests = new Map<number, PendingRequest>();
    private isReady = false;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private _starting = false; // Guard flag to prevent concurrent starts

    constructor() {
        super();
        this.useHttp = process.env.USE_CHAT_SERVER_HTTP === 'true';
        this.httpPort = parseInt(process.env.CHAT_SERVER_PORT || '8767', 10);
        this.httpBaseUrl = `http://localhost:${this.httpPort}`;
        
        this.pythonPath = process.env.PYTHON_PATH || 'python';
        this.serverScriptPath = this.useHttp
            ? path.join(__dirname, '..', '..', 'src', 'api', 'chat_server_http.py')
            : path.join(__dirname, '..', '..', 'src', 'api', 'chat_server.py');
        
        this.startServer();
    }
    
    startServer(): void {
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
        this.serverProcess.stderr?.on('data', (data: Buffer) => {
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
        this.serverProcess.stdout?.on('data', (data: Buffer) => {
            buffer += data.toString();
            
            // Process complete JSON lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const response = JSON.parse(line) as ChatResponse;
                        this.handleResponse(response);
                    } catch (error) {
                        const err = error as Error;
                        logger.error('[Chat] Failed to parse response:', { line, error: err.message });
                    }
                }
            }
        });
        
        // Handle process exit
        this.serverProcess.on('exit', (code: number | null) => {
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
        this.serverProcess.on('error', (error: Error) => {
            logger.error('[Chat] Server process error:', { error: error.message, stack: error.stack });
            this.isReady = false;
            this._starting = false; // Clear starting flag
        });
    }
    
    handleResponse(response: ChatResponse): void {
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
    
    processQueue(): void {
        while (this.requestQueue.length > 0 && this.isReady) {
            const request = this.requestQueue.shift();
            if (request) {
                this._sendRequestInternal(request);
            }
        }
    }
    
    async checkHttpServer(): Promise<void> {
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
    
    _sendRequestInternal(request: InternalRequest): void {
        if (!this.isReady) {
            this.requestQueue.push(request);
            return;
        }
        
        if (this.useHttp) {
            // HTTP mode - send HTTP request
            this._sendHttpRequest(request);
        } else {
            // stdin/stdout mode
            if (!this.serverProcess || !this.serverProcess.stdin) {
                this.requestQueue.push(request);
                return;
            }
            const requestJson = JSON.stringify(request) + '\n';
            this.serverProcess.stdin.write(requestJson);
        }
    }
    
    _sendHttpRequest(request: InternalRequest): void {
        const method = request.method;
        const params = request.params || {};
        
        let endpoint = '';
        let body: string | null = null;
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
        const options: http.RequestOptions = {
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
            res.on('data', (chunk: Buffer) => {
                data += chunk.toString();
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
                    const err = error as Error;
                    logger.error('[Chat] Failed to parse HTTP response:', { error: err.message, data });
                    this.handleResponse({
                        id: request.id,
                        error: `Failed to parse response: ${err.message}`,
                        result: null
                    });
                }
            });
        });
        
        req.on('error', (error: Error) => {
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
     * @param request - Request object with method and params
     * @returns Response from server
     */
    sendRequest(request: { method: string; params?: ChatRequestParams }): Promise<unknown> {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const fullRequest: InternalRequest = {
                id: requestId,
                method: request.method,
                params: request.params || {}
            };
            
            // Set timeout (100 seconds for chat requests - increased to match original timeout)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[Chat] Request timeout', { requestId, method: request.method });
                    reject(new Error('Chat request timeout'));
                }
            }, 100000);
            
            // Store pending request with timeout clearing
            this.pendingRequests.set(requestId, {
                resolve: (result: unknown) => {
                    clearTimeout(timeout);
                    resolve(result);
                },
                reject: (error: Error) => {
                    clearTimeout(timeout);
                    reject(error);
                }
            });
            
            // Send request
            this._sendRequestInternal(fullRequest);
        });
    }
    
    /**
     * Simple chat without RAG - direct LLM call
     * @param message - User's message
     * @param conversationHistory - Previous conversation messages
     * @returns Response from LLM
     */
    async chat(message: string, conversationHistory: Array<{ role: string; content: string }> = []): Promise<string> {
        try {
            const result = await this.sendRequest({
                method: 'chat',
                params: {
                    message: message,
                    history: conversationHistory.slice(-5), // Last 5 messages
                    temperature: 0.85,
                    max_tokens: 500
                }
            }) as { answer?: string; message?: string };
            
            return result.answer || result.message || 'Sorry, I could not generate a response.';
        } catch (error) {
            logger.error('[Chat] Error in chat:', error);
            throw error;
        }
    }
    
    shutdown(): void {
        if (this.serverProcess) {
            logger.info('[Chat] Shutting down persistent server...');
            this.serverProcess.kill();
            this.serverProcess = null;
            this.isReady = false;
        }
    }
}

// Export singleton instance
const chatService = new PersistentChatService();
export default chatService;

