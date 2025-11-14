/**
 * Persistent RAG Service that keeps Python RAG server alive.
 * Much faster than spawning new processes for each query.
 */
const { spawn } = require('child_process');
const path = require('path');
const EventEmitter = require('events');
const logger = require('./logger');

class PersistentRAGService extends EventEmitter {
    constructor() {
        super();
        this.pythonPath = process.env.PYTHON_PATH || 'python';
        this.serverScriptPath = path.join(__dirname, '..', '..', 'rag_server.py');
        this.serverProcess = null;
        this.requestQueue = [];
        this.requestId = 0;
        this.pendingRequests = new Map();
        this.isReady = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.startServer();
    }
    
    startServer() {
        if (this.serverProcess) {
            return; // Already started
        }
        
        logger.info('[RAG] Starting persistent RAG server...');
        
        this.serverProcess = spawn(this.pythonPath, [this.serverScriptPath], {
            stdio: ['pipe', 'pipe', 'pipe']
        });
        
        let startupOutput = '';
        
        // Handle stderr (debug output)
        this.serverProcess.stderr.on('data', (data) => {
            const output = data.toString();
            startupOutput += output;
            console.log(`[RAG Server] ${output.trim()}`);
            
            // Check if server is ready
            if (output.includes('RAG server ready!')) {
                this.isReady = true;
                this.reconnectAttempts = 0;
                logger.info('[RAG] Server ready! Processing queued requests...');
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
                        logger.error('[RAG] Failed to parse response:', { line, error: error.message });
                    }
                }
            }
        });
        
        // Handle process exit
        this.serverProcess.on('exit', (code) => {
            logger.error(`[RAG] Server process exited with code ${code}`);
            this.serverProcess = null;
            this.isReady = false;
            
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
        this.serverProcess.on('error', (error) => {
            logger.error('[RAG] Server process error:', { error: error.message, stack: error.stack });
            this.isReady = false;
        });
        
        // Send ping after a short delay to verify connection
        setTimeout(() => {
            if (!this.isReady) {
                this.ping();
            }
        }, 3000);
    }
    
    ping() {
        this.queryWithContext('ping', [], null, true).catch(() => {
            // Ignore ping errors
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
    
    queryWithContext(question, conversationHistory = [], userId = null, channelId = null, docId = null, docFilename = null, isPing = false) {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            // Clean the question but don't include full conversation history in the question
            // The RAG pipeline's memory system will handle retrieving relevant context
            // Only clean Discord mentions and special characters from the current question
            const cleanQuestion = isPing ? 'ping' : this._cleanDiscordText(question);
            
            // Truncate if too long (max 500 chars for the question itself)
            const truncatedQuestion = cleanQuestion.length > 500 
                ? cleanQuestion.substring(0, 500) + '...' 
                : cleanQuestion;
            
            const request = {
                id: requestId,
                method: isPing ? 'ping' : 'query',
                params: {
                    question: truncatedQuestion,  // Only send the current question, not full context
                    top_k: 10,
                    user_id: userId,  // Kept for backward compat
                    channel_id: channelId,  // New: channel-based memories
                    doc_id: docId,  // Filter to specific document by ID
                    doc_filename: docFilename,  // Filter to specific document by filename
                    use_memory: true,  // Memory system will retrieve relevant context
                    use_shared_docs: true,
                    use_hybrid_search: true,
                    use_query_expansion: true,
                    use_temporal_weighting: true
                }
            };
            
            logger.debug('[RAG] Sending query request', { 
                requestId, 
                questionLength: question.length,
                hasHistory: conversationHistory.length > 0,
                channelId,
                docId,
                docFilename 
            });
            
            // Store pending request
            this.pendingRequests.set(requestId, { resolve, reject });
            
            // Set timeout
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[RAG] Request timeout', { requestId, question: question.substring(0, 50) });
                    reject(new Error('RAG service timeout'));
                }
            }, isPing ? 5000 : 30000);  // Reduced from 60s to 30s for faster timeout and fallback
            
            // Override resolve/reject to clear timeout
            const originalResolve = resolve;
            const originalReject = reject;
            this.pendingRequests.set(requestId, {
                resolve: (result) => {
                    clearTimeout(timeout);
                    logger.debug('[RAG] Request completed', { requestId, answerLength: result?.answer?.length || 0 });
                    originalResolve(result);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    logger.error('[RAG] Request failed', { requestId, error: error.message });
                    originalReject(error);
                }
            });
            
            // Send request
            this.sendRequest(request);
        });
    }
    
    // DEPRECATED: This method is no longer used. Conversation history is handled by the RAG pipeline's memory system.
    // Keeping it for backward compatibility but it should not be used for building query prompts.
    buildContextPrompt(currentQuestion, conversationHistory) {
        // Clean Discord mentions and special characters from question
        const cleanQuestion = this._cleanDiscordText(currentQuestion);
        
        // Don't include conversation history in the question - let the memory system handle it
        // Just return the cleaned question
        return cleanQuestion.length > 500 ? cleanQuestion.substring(0, 500) + '...' : cleanQuestion;
    }
    
    _cleanDiscordText(text) {
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
    
    shutdown() {
        if (this.serverProcess) {
            logger.info('[RAG] Shutting down persistent server...');
            this.serverProcess.kill();
            this.serverProcess = null;
            this.isReady = false;
        }
    }
}

module.exports = PersistentRAGService;

