/**
 * Refactored RAG Service using HTTP client.
 * Connects to the refactored RAG HTTP server.
 */
import * as http from 'http';
import * as https from 'https';
import { URL } from 'url';
import logger from './logger.js';
import type { RAGRequest, RAGResponse, RAGResult } from './types/services.js';

export interface RAGQueryParams {
    question: string;
    top_k?: number;
    temperature?: number;
    max_tokens?: number;
    max_context_tokens?: number;
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
    username?: string;
}

class RefactoredRAGService {
    private host: string;
    private port: number;
    private timeout: number;
    private useHttps: boolean;

    constructor() {
        this.host = process.env.REFACTORED_RAG_HOST || 'localhost';
        this.port = parseInt(process.env.REFACTORED_RAG_PORT || '8767', 10);
        this.timeout = parseInt(process.env.REFACTORED_RAG_TIMEOUT || '120000', 10); // 120 seconds default
        this.useHttps = process.env.REFACTORED_RAG_HTTPS === 'true';
    }

    /**
     * Query the RAG system
     */
    async query(params: RAGQueryParams): Promise<RAGResult> {
        const result = await this._makeRequest('/query', params);
        // Convert to RAGResult format
        return {
            answer: result.answer || '',
            context_chunks: result.context_chunks || 0,
            memories_used: result.memories_used || 0,
            question: result.question || params.question,
            source_documents: result.source_documents || [],
            source_memories: result.source_memories || [],
            timing: result.timing || {},
            is_casual_conversation: result.is_casual_conversation || false,
            service_routing: result.service_routing || 'rag',
            tool_calls: result.tool_calls || []
        };
    }

    /**
     * Query with context (compatibility method)
     */
    async queryWithContext(
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
        if (isPing) {
            // Handle ping separately
            try {
                await this.healthCheck();
                return {
                    answer: 'pong',
                    context_chunks: 0,
                    memories_used: 0,
                    question: 'ping',
                    source_documents: [],
                    source_memories: [],
                    timing: {},
                    is_casual_conversation: false,
                    service_routing: 'rag',
                    tool_calls: []
                };
            } catch (error) {
                throw new Error(`RAG service ping failed: ${(error as Error).message}`);
            }
        }

        // Extract mentioned user ID from question if not provided
        let extractedMentionedUserId = mentionedUserId;
        if (!extractedMentionedUserId) {
            const mentionMatch = question.match(/<@!?(\d+)>/);
            if (mentionMatch) {
                extractedMentionedUserId = mentionMatch[1];
            }
        }

        // Truncate if too long
        const truncatedQuestion = question.length > 500 
            ? question.substring(0, 500) + '...' 
            : question;

        return this.query({
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
        });
    }

    /**
     * Query using JSON-RPC format (for compatibility)
     */
    async queryJSONRPC(request: RAGRequest): Promise<RAGResponse> {
        return this._makeRequest('/query_jsonrpc', request) as Promise<RAGResponse>;
    }

    /**
     * Send conversation request (for compatibility with conversation manager)
     */
    async sendConversationRequest(request: { method: string; params?: Record<string, unknown> }): Promise<unknown> {
        // For now, return empty result - conversation history is handled by RAG pipeline memory
        if (request.method === 'get_conversation') {
            return {
                result: {
                    messages: []
                },
                error: null
            };
        }
        
        // For other methods, return error
        return {
            result: null,
            error: `Method ${request.method} not supported by refactored RAG service`
        };
    }

    /**
     * Shutdown (no-op for HTTP service, kept for compatibility)
     */
    shutdown(): void {
        // HTTP service doesn't need shutdown
        logger.info('[RAG] Refactored RAG service shutdown called (no-op for HTTP service)');
    }

    /**
     * Health check
     */
    async healthCheck(): Promise<{ status: string; initialized: boolean }> {
        return this._makeRequest('/health', null, 'GET') as Promise<{ status: string; initialized: boolean }>;
    }

    /**
     * Make HTTP request to RAG server
     */
    private _makeRequest(endpoint: string, data: any, method: string = 'POST'): Promise<any> {
        return new Promise((resolve, reject) => {
            const url = new URL(`http${this.useHttps ? 's' : ''}://${this.host}:${this.port}${endpoint}`);
            
            const postData = data ? JSON.stringify(data) : null;
            const options = {
                hostname: url.hostname,
                port: url.port,
                path: url.pathname,
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': postData ? Buffer.byteLength(postData) : 0
                },
                timeout: this.timeout
            };

            const httpModule = this.useHttps ? https : http;
            const req = httpModule.request(options, (res) => {
                let responseData = '';

                res.on('data', (chunk) => {
                    responseData += chunk.toString();
                });

                res.on('end', () => {
                    if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
                        try {
                            const result = JSON.parse(responseData);
                            resolve(result);
                        } catch (error) {
                            const err = error as Error;
                            reject(new Error(`Failed to parse response: ${err.message}`));
                        }
                    } else {
                        reject(new Error(`HTTP ${res.statusCode}: ${responseData}`));
                    }
                });
            });

            req.on('error', (error) => {
                logger.error(`Refactored RAG HTTP request failed: ${error.message}`);
                reject(new Error(`HTTP request failed: ${error.message}`));
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Refactored RAG HTTP request timeout'));
            });

            if (postData) {
                req.write(postData);
            }
            req.end();
        });
    }
}

// Export singleton instance
const refactoredRagService = new RefactoredRAGService();
export default refactoredRagService;

