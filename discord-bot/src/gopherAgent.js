/**
 * GopherAgent - JavaScript wrapper for Python GopherAgent
 * Provides fast, agentic message routing for Discord bot.
 */
const { spawn } = require('child_process');
const path = require('path');
const logger = require('./logger');

class GopherAgent {
    constructor() {
        this.pythonPath = process.env.PYTHON_PATH || 'python';
        this.agentScript = path.join(__dirname, '..', '..', 'src', 'agents', 'gopher_agent_api.py');
        this.cache = new Map();
        this.cacheTTL = 5 * 60 * 1000; // 5 minutes
        this.pendingRequests = new Map();
        this.timeout = 15000; // 15 second timeout (increased for LLM inference overhead)
        
        // Try HTTP server first (faster), fallback to subprocess
        this.useHttpServer = process.env.GOPHER_AGENT_HTTP === 'true';
        this.httpBaseUrl = process.env.GOPHER_AGENT_URL || 'http://localhost:8765';
        
        logger.info(`🤖 GopherAgent initialized (mode: ${this.useHttpServer ? 'HTTP' : 'subprocess'})`);
    }
    
    /**
     * Classify message intent using GopherAgent
     * @param {string} message - Message text
     * @param {Object} context - Context (hasAttachments, isMentioned, recentMessages, etc.)
     * @returns {Promise<Object>} Intent classification result
     */
    async classifyIntent(message, context = {}) {
        // Check cache first
        const cacheKey = this._getCacheKey(message, context);
        const cached = this.cache.get(cacheKey);
        if (cached && Date.now() - cached.timestamp < this.cacheTTL) {
            logger.debug('GopherAgent cache hit');
            return { ...cached.data, cached: true };
        }
        
        // Check if request is already pending (deduplication)
        if (this.pendingRequests.has(cacheKey)) {
            logger.debug('GopherAgent request deduplication');
            return await this.pendingRequests.get(cacheKey);
        }
        
        // Create new request
        const requestPromise = this._callPythonAgent('classify_intent', {
            message,
            context
        });
        
        this.pendingRequests.set(cacheKey, requestPromise);
        
        try {
            const result = await requestPromise;
            
            // Cache result
            this.cache.set(cacheKey, {
                data: result,
                timestamp: Date.now()
            });
            
            // Clean up pending request
            this.pendingRequests.delete(cacheKey);
            
            return { ...result, cached: false };
        } catch (error) {
            this.pendingRequests.delete(cacheKey);
            // If timeout, return fallback result instead of throwing
            if (error.code === 'TIMEOUT' || error.message.includes('timeout')) {
                logger.warn(`GopherAgent ${method} timeout, using fallback`);
                return this._getFallbackResult(message, context, method);
            }
            throw error;
        }
    }
    
    /**
     * Route message to appropriate handler
     * @param {string} message - Message text
     * @param {Object} context - Context
     * @param {Object} intentResult - Pre-computed intent (optional)
     * @returns {Promise<Object>} Routing result
     */
    async routeMessage(message, context = {}, intentResult = null) {
        // Get intent if not provided
        if (!intentResult) {
            intentResult = await this.classifyIntent(message, context);
        }
        
        // Route based on intent
        const intent = intentResult.intent || 'ignore';
        const routing = intentResult.routing || 'chat';
        const shouldRespond = intentResult.should_respond !== false;
        
        // Determine handler
        let handler = 'ignore';
        if (!shouldRespond) {
            handler = 'ignore';
        } else if (intent === 'upload' || context.hasAttachments) {
            handler = 'upload';
        } else if (intent === 'action' || routing === 'action') {
            handler = 'action';
        } else if (routing === 'rag' || intentResult.needs_rag) {
            handler = 'rag';
        } else if (routing === 'tools' || intentResult.needs_tools) {
            handler = 'tools';
        } else if (routing === 'memory' || intentResult.needs_memory) {
            handler = 'memory';
        } else if (routing === 'chat' || intent === 'casual') {
            handler = 'chat';
        } else {
            handler = 'chat'; // Default fallback
        }
        
        return {
            handler,
            intent: intentResult,
            routing_confidence: intentResult.confidence || 0.5
        };
    }
    
    /**
     * Batch classify multiple messages
     * @param {Array<{message: string, context: Object}>} messages - Messages to classify
     * @returns {Promise<Array<Object>>} Classification results
     */
    async batchClassify(messages) {
        return await this._callPythonAgent('batch_classify', { messages });
    }
    
    /**
     * Get performance metrics
     * @returns {Promise<Object>} Metrics
     */
    async getMetrics() {
        return await this._callPythonAgent('get_metrics', {});
    }
    
    /**
     * Clear cache
     */
    clearCache() {
        this.cache.clear();
        logger.info('GopherAgent cache cleared');
    }
    
    /**
     * Call Python GopherAgent API (HTTP or subprocess)
     * @private
     */
    _callPythonAgent(method, params) {
        // Try HTTP server first if enabled
        if (this.useHttpServer) {
            return this._callHttpAgent(method, params);
        }
        
        // Fallback to subprocess
        return this._callSubprocessAgent(method, params);
    }
    
    /**
     * Call GopherAgent via HTTP (faster)
     * @private
     */
    async _callHttpAgent(method, params) {
        const axios = require('axios');
        const endpoint = method === 'classify_intent' ? '/classify_intent' :
                        method === 'route_message' ? '/route_message' :
                        method === 'get_metrics' ? '/get_metrics' : null;
        
        if (!endpoint) {
            throw new Error(`Unknown method: ${method}`);
        }
        
        try {
            const response = await axios.post(`${this.httpBaseUrl}${endpoint}`, params, {
                timeout: this.timeout,
                headers: { 'Content-Type': 'application/json' }
            });
            return response.data;
        } catch (error) {
            logger.warn(`GopherAgent HTTP call failed, falling back to subprocess: ${error.message}`);
            // Fallback to subprocess
            return this._callSubprocessAgent(method, params);
        }
    }
    
    /**
     * Call Python GopherAgent API via subprocess
     * @private
     */
    _callSubprocessAgent(method, params) {
        return new Promise((resolve, reject) => {
            const args = [
                this.agentScript,
                '--method', method,
                '--params', JSON.stringify(params)
            ];
            
            // Set working directory to project root for proper Python imports
            const projectRoot = path.join(__dirname, '..', '..');
            
            const pythonProcess = spawn(this.pythonPath, args, {
                stdio: ['pipe', 'pipe', 'pipe'],
                cwd: projectRoot,
                env: {
                    ...process.env,
                    PYTHONPATH: projectRoot  // Add project root to PYTHONPATH
                }
            });
            
            let stdout = '';
            let stderr = '';
            
            const timeout = setTimeout(() => {
                pythonProcess.kill('SIGTERM');
                // Give it a moment to clean up, then force kill
                setTimeout(() => {
                    try {
                        pythonProcess.kill('SIGKILL');
                    } catch (e) {
                        // Process already dead
                    }
                }, 1000);
                const error = new Error(`GopherAgent ${method} timeout after ${this.timeout}ms`);
                error.code = 'TIMEOUT';
                reject(error);
            }, this.timeout);
            
            pythonProcess.stdout.on('data', (data) => {
                stdout += data.toString();
            });
            
            pythonProcess.stderr.on('data', (data) => {
                stderr += data.toString();
            });
            
            pythonProcess.on('close', (code) => {
                clearTimeout(timeout);
                
                if (code !== 0) {
                    logger.error(`GopherAgent error (code ${code}): ${stderr}`);
                    reject(new Error(`GopherAgent error: ${stderr || 'Unknown error'}`));
                    return;
                }
                
                try {
                    // Extract JSON from stdout
                    const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                    if (jsonMatch) {
                        const result = JSON.parse(jsonMatch[0]);
                        resolve(result);
                    } else {
                        reject(new Error('Invalid response from GopherAgent'));
                    }
                } catch (error) {
                    logger.error(`Failed to parse GopherAgent response: ${stdout.substring(0, 500)}`);
                    reject(error);
                }
            });
            
            pythonProcess.on('error', (error) => {
                clearTimeout(timeout);
                reject(new Error(`Failed to start GopherAgent: ${error.message}`));
            });
        });
    }
    
    /**
     * Generate cache key
     * @private
     */
    _getCacheKey(message, context) {
        const keyData = {
            message: message.toLowerCase().trim(),
            hasAttachments: context.hasAttachments || false,
            isMentioned: context.isMentioned || false
        };
        return JSON.stringify(keyData);
    }
    
    /**
     * Get fallback result when GopherAgent times out or fails
     * @private
     */
    _getFallbackResult(message, context, method) {
        const messageLower = message.toLowerCase();
        
        // Quick pattern-based fallback
        const hasUrl = /https?:\/\//.test(message) || /youtube\.com|youtu\.be/.test(messageLower);
        const hasAttachment = context.hasAttachments;
        const isGreeting = /^(hi|hello|hey|greetings)/i.test(message.trim());
        
        if (method === 'classify_intent') {
            if (hasUrl) {
                return {
                    intent: 'question',
                    should_respond: true,
                    confidence: 0.8,
                    routing: 'tools',
                    needs_rag: false,
                    needs_tools: true,
                    needs_memory: false,
                    is_casual: false,
                    document_references: [],
                    fallback: true
                };
            }
            if (hasAttachment) {
                return {
                    intent: 'upload',
                    should_respond: true,
                    confidence: 0.9,
                    routing: 'upload',
                    needs_rag: false,
                    needs_tools: false,
                    needs_memory: false,
                    is_casual: false,
                    document_references: [],
                    fallback: true
                };
            }
            if (isGreeting) {
                return {
                    intent: 'casual',
                    should_respond: true,
                    confidence: 0.7,
                    routing: 'chat',
                    needs_rag: false,
                    needs_tools: false,
                    needs_memory: false,
                    is_casual: true,
                    document_references: [],
                    fallback: true
                };
            }
            // Default: treat as question needing RAG
            return {
                intent: 'question',
                should_respond: true,
                confidence: 0.5,
                routing: 'rag',
                needs_rag: true,
                needs_tools: false,
                needs_memory: false,
                is_casual: false,
                document_references: [],
                fallback: true
            };
        }
        
        // Fallback for route_message
        return {
            handler: hasUrl ? 'tools' : (isGreeting ? 'chat' : 'rag'),
            intent: this._getFallbackResult(message, context, 'classify_intent'),
            routing_confidence: 0.5,
            fallback: true
        };
    }
}

module.exports = new GopherAgent();

