/**
 * Persistent RAG Service that keeps Python RAG server alive.
 * Much faster than spawning new processes for each query.
 */
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import { EventEmitter } from 'events';
import logger from './logger.js';
import type { RAGRequest, RAGResponse, RAGResult } from './types/services.js';

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

interface QueryParams {
    question: string;
    top_k?: number;
    user_id?: string | null;
    channel_id?: string | null;
    doc_id?: string | null;
    doc_filename?: string | null;
    mentioned_user_id?: string | null;
    is_admin?: boolean;
    use_memory?: boolean;
    use_shared_docs?: boolean;
    use_hybrid_search?: boolean;
    use_query_expansion?: boolean;
    use_temporal_weighting?: boolean;
}

class PersistentRAGService extends EventEmitter {
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
        this.serverScriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'rag_server.py');
        
        this.startServer();
    }
    
    startServer(): void {
        // CRITICAL: Prevent concurrent server starts
        if (this.serverProcess || this._starting) {
            logger.debug('[RAG] Server already started or starting, skipping...');
            return; // Already started or starting
        }
        
        this._starting = true;
        
        logger.info('[RAG] Starting persistent RAG server...');
        
        this.serverProcess = spawn(this.pythonPath, [this.serverScriptPath], {
            stdio: ['pipe', 'pipe', 'pipe']
        });
        
        let startupOutput = '';
        
        // Handle stderr (debug output)
        this.serverProcess.stderr?.on('data', (data: Buffer) => {
            const output = data.toString();
            startupOutput += output;
            console.log(`[RAG Server] ${output.trim()}`);
            
            // Check if server is ready
            if (output.includes('RAG server ready!')) {
                this.isReady = true;
                this._starting = false; // Clear starting flag
                this.reconnectAttempts = 0;
                logger.info('[RAG] Server ready! Processing queued requests...');
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
                        const response = JSON.parse(line) as RAGResponse;
                        this.handleResponse(response);
                    } catch (error) {
                        const err = error as Error;
                        logger.error('[RAG] Failed to parse response:', { line, error: err.message });
                    }
                }
            }
        });
        
        // Handle process exit
        this.serverProcess.on('exit', (code: number | null) => {
            logger.error(`[RAG] Server process exited with code ${code}`);
            this.serverProcess = null;
            this.isReady = false;
            this._starting = false; // Clear starting flag
            
            // Attempt to reconnect
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                logger.warn(`[RAG] Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
                setTimeout(() => this.startServer(), 2000);
            } else {
                logger.error('[RAG] Max reconnection attempts reached. Server unavailable.');
            }
        });
        
        // Handle errors
        this.serverProcess.on('error', (error: Error) => {
            logger.error('[RAG] Server process error:', { error: error.message, stack: error.stack });
            this.isReady = false;
            this._starting = false; // Clear starting flag
        });
    }
    
    handleResponse(response: RAGResponse): void {
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
     * Send a conversation management request to the RAG server
     * @param request - Request object with method and params
     * @returns Response from server
     */
    sendConversationRequest(request: { method: string; params?: Record<string, unknown> }): Promise<unknown> {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const fullRequest: InternalRequest = {
                id: requestId,
                method: request.method,
                params: request.params || {}
            };
            
            // Set timeout (90 seconds for conversation requests - Neo4j queries can take time, especially under load or with deadlocks)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[RAG] Conversation request timeout', { requestId, method: request.method });
                    reject(new Error('Conversation request timeout'));
                }
            }, 90000);
            
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
            this.sendRequest(fullRequest);
        });
    }
    
    queryWithContext(
        question: string,
        conversationHistory: Array<{ role: string; content: string }> = [],
        userId: string | null = null,
        channelId: string | null = null,
        docId: string | null = null,
        docFilename: string | null = null,
        isPing = false,
        mentionedUserId: string | null = null,
        isAdmin = false
    ): Promise<RAGResult> {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            // Extract mentioned user ID from question BEFORE cleaning (in case it wasn't passed)
            let extractedMentionedUserId = mentionedUserId;
            if (!extractedMentionedUserId) {
                const mentionMatch = question.match(/<@!?(\d+)>/);
                if (mentionMatch) {
                    extractedMentionedUserId = mentionMatch[1];
                }
            }
            
            // For action commands, we need to preserve mentions in the question
            const questionToSend = isPing ? 'ping' : question;
            
            // Truncate if too long (max 500 chars for the question itself)
            const truncatedQuestion = questionToSend.length > 500 
                ? questionToSend.substring(0, 500) + '...' 
                : questionToSend;
            
            const params: QueryParams = {
                question: truncatedQuestion,
                top_k: 10,
                user_id: userId,
                channel_id: channelId,
                doc_id: docId,
                doc_filename: docFilename,
                mentioned_user_id: extractedMentionedUserId,
                is_admin: isAdmin,
                use_memory: true,
                use_shared_docs: true,
                use_hybrid_search: true,
                use_query_expansion: true,
                use_temporal_weighting: true
            };
            
            const request: InternalRequest = {
                id: requestId,
                method: isPing ? 'ping' : 'query',
                params
            };
            
            logger.debug('[RAG] Sending query request', { 
                requestId, 
                questionLength: question.length,
                hasHistory: conversationHistory.length > 0,
                channelId,
                docId,
                docFilename 
            });
            
            // Check if this is a URL request (YouTube or website) - these take longer
            const hasUrl = question && (
                question.includes('http://') || 
                question.includes('https://') || 
                question.includes('youtube.com') || 
                question.includes('youtu.be') ||
                question.includes('www.')
            );
            
            // Check if this is an image generation request - these take longer (RunPod API can take 30-120s)
            const cleanedQuestionForTimeout = question ? question
                .replace(/<@!?\d+>/g, '')
                .replace(/<@&\d+>/g, '')
                .replace(/<#\d+>/g, '')
                .replace(/\s+/g, ' ')
                .trim() : '';
            
            const hasImageGeneration = question && (
                /generate\s+(?:an?\s+)?(?:image|picture|artwork|art)/i.test(question) ||
                /create\s+(?:an?\s+)?(?:image|picture|artwork|art)/i.test(question) ||
                /make\s+(?:an?\s+)?(?:image|picture|artwork|art)/i.test(question) ||
                /draw\s+(?:an?\s+)?(?:image|picture|artwork|art)/i.test(question) ||
                /generate\s+(?:an?\s+)?(?:image|picture|artwork|art)/i.test(cleanedQuestionForTimeout) ||
                /create\s+(?:an?\s+)?(?:image|picture|artwork|art)/i.test(cleanedQuestionForTimeout) ||
                /make\s+(?:an?\s+)?(?:image|picture|artwork|art)/i.test(cleanedQuestionForTimeout) ||
                /draw\s+(?:an?\s+)?(?:image|picture|artwork|art)/i.test(cleanedQuestionForTimeout)
            );
            
            if (hasImageGeneration) {
                logger.info(`[RAG] Image generation detected - using 15min timeout for question: "${question.substring(0, 100)}"`);
            }
            
            // For URL requests, wait for tool completion - use a very long safety net timeout (10 minutes)
            // This is only for truly stuck requests, not for normal processing
            // YouTube/website processing can take several minutes - we want to wait for the complete result
            // Image generation can take 5-15 minutes (job queuing, processing, polling, decoding) - use 15min timeout
            const timeoutDuration = isPing ? 5000 : (hasImageGeneration ? 900000 : (hasUrl ? 600000 : 60000)); // 15min for images, 10min for URLs
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[RAG] Request timeout', { requestId, question: question.substring(0, 50), timeoutDuration });
                    reject(new Error('RAG service timeout'));
                }
            }, timeoutDuration);
            
            // Store pending request with timeout clearing
            this.pendingRequests.set(requestId, {
                resolve: (result: unknown) => {
                    clearTimeout(timeout);
                    logger.debug('[RAG] Request completed', { requestId, answerLength: (result as RAGResult)?.answer?.length || 0 });
                    resolve(result as RAGResult);
                },
                reject: (error: Error) => {
                    clearTimeout(timeout);
                    logger.error('[RAG] Request failed', { requestId, error: error.message });
                    reject(error);
                }
            });
            
            // Send request
            this.sendRequest(request);
        });
    }
    
    // DEPRECATED: This method is no longer used. Conversation history is handled by the RAG pipeline's memory system.
    buildContextPrompt(currentQuestion: string, conversationHistory: Array<{ role: string; content: string }>): string {
        // Clean Discord mentions and special characters from question
        const cleanQuestion = this._cleanDiscordText(currentQuestion);
        
        // Don't include conversation history in the question - let the memory system handle it
        return cleanQuestion.length > 500 ? cleanQuestion.substring(0, 500) + '...' : cleanQuestion;
    }
    
    private _cleanDiscordText(text: string): string {
        if (!text || typeof text !== 'string') {
            return '';
        }
        
        // Remove Discord mentions: <@123456789>, <@!123456789>, <@&123456789>, <#123456789>
        text = text.replace(/<@!?\d+>/g, '');
        text = text.replace(/<@&\d+>/g, '');
        text = text.replace(/<#\d+>/g, '');
        text = text.replace(/<:\w+:\d+>/g, ''); // Remove custom emojis
        text = text.replace(/<a:\w+:\d+>/g, ''); // Remove animated emojis
        
        // Remove URLs but keep the domain for context
        text = text.replace(/https?:\/\/[^\s]+/g, '');
        
        // Remove excessive whitespace
        text = text.replace(/\s+/g, ' ').trim();
        
        return text;
    }
    
    shutdown(): void {
        if (this.serverProcess) {
            logger.info('[RAG] Shutting down persistent server...');
            this.serverProcess.kill();
            this.serverProcess = null;
            this.isReady = false;
        }
    }
}

export default PersistentRAGService;

