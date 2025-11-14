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
        this.serverScriptPath = path.join(__dirname, '..', '..', 'src', 'api', 'rag_server.py');
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
    
    /**
     * Send a conversation management request to the RAG server
     * @param {Object} request - Request object with method and params
     * @returns {Promise<Object>} Response from server
     */
    sendConversationRequest(request) {
        return new Promise((resolve, reject) => {
            const requestId = ++this.requestId;
            
            const fullRequest = {
                id: requestId,
                method: request.method,
                params: request.params || {}
            };
            
            // Store pending request
            this.pendingRequests.set(requestId, { resolve, reject });
            
            // Set timeout (10 seconds for conversation requests - Neo4j queries can take time)
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[RAG] Conversation request timeout', { requestId, method: request.method });
                    reject(new Error('Conversation request timeout'));
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
            this.sendRequest(fullRequest);
        });
    }
    
    queryWithContext(question, conversationHistory = [], userId = null, channelId = null, docId = null, docFilename = null, isPing = false, mentionedUserId = null, isAdmin = false) {
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
            // The RAG pipeline will handle cleaning internally for document search
            // But action parsing needs the original question with mentions
            const questionToSend = isPing ? 'ping' : question;
            
            // Truncate if too long (max 500 chars for the question itself)
            const truncatedQuestion = questionToSend.length > 500 
                ? questionToSend.substring(0, 500) + '...' 
                : questionToSend;
            
            const request = {
                id: requestId,
                method: isPing ? 'ping' : 'query',
                params: {
                    question: truncatedQuestion,  // Send original question with mentions for action parsing
                    top_k: 10,
                    user_id: userId,  // Kept for backward compat
                    channel_id: channelId,  // New: channel-based memories
                    doc_id: docId,  // Filter to specific document by ID
                    doc_filename: docFilename,  // Filter to specific document by filename
                    mentioned_user_id: extractedMentionedUserId,  // Pass mentioned user ID for state queries
                    is_admin: isAdmin,  // Pass admin status for tool creation permissions
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
            
            // Check if this is a URL request (YouTube or website) - these take longer
            const hasUrl = question && (
                question.includes('http://') || 
                question.includes('https://') || 
                question.includes('youtube.com') || 
                question.includes('youtu.be') ||
                question.includes('www.')
            );
            
            // Set timeout - longer for URL requests (90s) since they need to fetch transcript, chunk it, and summarize multiple chunks
            // YouTube summarization can take 30-60 seconds for chunk processing alone
            const timeoutDuration = isPing ? 5000 : (hasUrl ? 90000 : 30000);
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    logger.warn('[RAG] Request timeout', { requestId, question: question.substring(0, 50), timeoutDuration });
                    reject(new Error('RAG service timeout'));
                }
            }, timeoutDuration);
            
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

