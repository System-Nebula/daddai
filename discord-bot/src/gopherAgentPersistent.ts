/**
 * Persistent GopherAgent Service that keeps Python server alive.
 * Much faster than spawning new processes for each request.
 */
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import { EventEmitter } from 'events';
import logger from './logger';
import type { GopherAgentRequest, GopherAgentResponse, GopherAgentResult } from './types';

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface PendingRequest {
    resolve: (result: unknown) => void;
    reject: (error: Error) => void;
}

interface InternalRequest {
    id: number;
    method: string;
    params: Record<string, unknown>;
}

interface RouteMessageContext {
    hasAttachments?: boolean;
    has_attachments?: boolean;
    isMentioned?: boolean;
    is_mentioned?: boolean;
    userId?: string;
    channelId?: string;
    guildId?: string;
    recentMessages?: Array<{ role: string; content: string }>;
    [key: string]: unknown;
}

class PersistentGopherAgentService extends EventEmitter {
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
        this.pythonPath = process.env.PYTHON_PATH || 'python';
        this.serverScriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'gopher_agent_persistent_server.py');
        
        this.startServer();
    }
    
    startServer(): void {
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
        this.serverProcess.stderr?.on('data', (data: Buffer) => {
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
        this.serverProcess.stdout?.on('data', (data: Buffer) => {
            buffer += data.toString();
            
            // Process complete JSON lines
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const response = JSON.parse(line) as GopherAgentResponse;
                        this.handleResponse(response);
                    } catch (error) {
                        const err = error as Error;
                        logger.error('[GopherAgent] Failed to parse response:', { line, error: err.message });
                    }
                }
            }
        });
        
        // Handle process exit
        this.serverProcess.on('exit', (code: number | null) => {
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
        this.serverProcess.on('error', (error: Error) => {
            logger.error('[GopherAgent] Server process error:', { error: error.message, stack: error.stack });
            this.isReady = false;
            this._starting = false; // Clear starting flag
        });
    }
    
    handleResponse(response: GopherAgentResponse): void {
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
                this.sendRequest(request);
            }
        }
    }
    
    sendRequest(request: InternalRequest): void {
        if (!this.isReady || !this.serverProcess || !this.serverProcess.stdin) {
            this.requestQueue.push(request);
            return;
        }
        
        const requestJson = JSON.stringify(request) + '\n';
        this.serverProcess.stdin.write(requestJson);
    }
    
    /**
     * Route message to appropriate handler
     * @param message - User's message
     * @param context - Context object (has_attachments, is_mentioned, etc.)
     * @param intentResult - Optional pre-computed intent result
     * @returns Routing result with handler, intent, etc.
     */
    async routeMessage(message: string, context: RouteMessageContext = {}, intentResult: GopherAgentResult['intent'] | null = null): Promise<GopherAgentResult['routing']> {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const request: InternalRequest = {
                id: requestId,
                method: 'route_message',
                params: {
                    message: message,
                    context: context,
                    intent_result: intentResult
                }
            };
            
            // Set timeout (10 seconds - balanced for LLM classification)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[GopherAgent] Request timeout', { requestId, method: 'route_message' });
                    reject(new Error('GopherAgent request timeout'));
                }
            }, 10000);
            
            // Store pending request with timeout clearing
            this.pendingRequests.set(requestId, {
                resolve: (result: unknown) => {
                    clearTimeout(timeout);
                    resolve(result as GopherAgentResult['routing']);
                },
                reject: (error: Error) => {
                    clearTimeout(timeout);
                    reject(error);
                }
            });
            
            // Send request
            this.sendRequest(request);
        });
    }
    
    /**
     * Classify message intent
     * @param message - User's message
     * @param context - Context object
     * @param useCache - Whether to use cache
     * @returns Intent classification result
     */
    async classifyIntent(message: string, context: RouteMessageContext = {}, useCache = true): Promise<GopherAgentResult['intent']> {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const request: InternalRequest = {
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
                resolve: (result: unknown) => {
                    clearTimeout(timeout);
                    originalResolve(result as GopherAgentResult['intent']);
                },
                reject: (error: Error) => {
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
     * @returns Metrics object
     */
    async getMetrics(): Promise<Record<string, unknown>> {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const request: InternalRequest = {
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
                resolve: (result: unknown) => {
                    clearTimeout(timeout);
                    originalResolve(result as Record<string, unknown>);
                },
                reject: (error: Error) => {
                    clearTimeout(timeout);
                    originalReject(error);
                }
            });
            
            // Send request
            this.sendRequest(request);
        });
    }
    
    /**
     * Check if agentic mode should be used
     * @param message - User's message
     * @param intentResult - Optional pre-computed intent result
     * @returns True if agentic mode should be used
     */
    async shouldUseAgenticMode(message: string, intentResult: Record<string, unknown> | null = null): Promise<boolean> {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const request: InternalRequest = {
                id: requestId,
                method: 'should_use_agentic_mode',
                params: {
                    message: message,
                    intent_result: intentResult
                }
            };
            
            // Store pending request
            this.pendingRequests.set(requestId, { resolve, reject });
            
            // Set timeout (3 seconds - should be instant for keyword check)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    reject(new Error('GopherAgent should_use_agentic_mode timeout'));
                }
            }, 3000);
            
            // Override resolve/reject to clear timeout
            const originalResolve = resolve;
            const originalReject = reject;
            this.pendingRequests.set(requestId, {
                resolve: (result: unknown) => {
                    clearTimeout(timeout);
                    originalResolve(result as boolean);
                },
                reject: (error: Error) => {
                    clearTimeout(timeout);
                    originalReject(error);
                }
            });
            
            // Send request
            this.sendRequest(request);
        });
    }
    
    /**
     * Run an agentic task using ReAct pattern
     * @param message - User's message/task
     * @param context - Context object
     * @returns Agentic task result
     */
    async runAgenticTask(message: string, context: RouteMessageContext = {}): Promise<Record<string, unknown>> {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const request: InternalRequest = {
                id: requestId,
                method: 'run_agentic_task',
                params: {
                    message: message,
                    context: context
                }
            };
            
            // Store pending request
            this.pendingRequests.set(requestId, { resolve, reject });
            
            // Set timeout (60 seconds for agentic tasks)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    reject(new Error('GopherAgent run_agentic_task timeout'));
                }
            }, 60000);
            
            // Override resolve/reject to clear timeout
            const originalResolve = resolve;
            const originalReject = reject;
            this.pendingRequests.set(requestId, {
                resolve: (result: unknown) => {
                    clearTimeout(timeout);
                    originalResolve(result as Record<string, unknown>);
                },
                reject: (error: Error) => {
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
const gopherAgentService = new PersistentGopherAgentService();
export default gopherAgentService;

