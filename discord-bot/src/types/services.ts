/**
 * Type definitions for Discord bot services
 */

export interface ChatRequest {
    id: number;
    method: string;
    params: {
        message: string;
        context?: ChatContext;
        [key: string]: unknown;
    };
}

export interface ChatResponse {
    id: number;
    result?: string | ChatResult;
    error?: string;
}

export interface ChatResult {
    response: string;
    metadata?: Record<string, unknown>;
}

export interface ChatContext {
    userId?: string;
    channelId?: string;
    guildId?: string;
    recentMessages?: Array<{ role: string; content: string }>;
    hasAttachments?: boolean;
    isMentioned?: boolean;
}

export interface RAGRequest {
    id: number;
    method: string;
    params: {
        query: string;
        userId: string;
        topK?: number;
        [key: string]: unknown;
    };
}

export interface RAGResponse {
    id: number;
    result?: RAGResult;
    error?: string;
}

export interface RAGResult {
    answer: string;
    sources?: Array<{ document: string; chunk: string; score: number }>;
    metadata?: Record<string, unknown>;
}

export interface MemoryRequest {
    id: number;
    method: string;
    params: {
        userId: string;
        query?: string;
        memory?: string;
        [key: string]: unknown;
    };
}

export interface MemoryResponse {
    id: number;
    result?: MemoryResult;
    error?: string;
}

export interface MemoryResult {
    memories?: Array<{ id: string; content: string; metadata?: Record<string, unknown> }>;
    memoryId?: string;
    success?: boolean;
}

export interface GopherAgentRequest {
    id: number;
    method: string;
    params: {
        message: string;
        context?: ChatContext;
        [key: string]: unknown;
    };
}

export interface GopherAgentResponse {
    id: number;
    result?: GopherAgentResult;
    error?: string;
}

export interface GopherAgentResult {
    intent: {
        intent: string;
        should_respond: boolean;
        confidence: number;
        routing: string;
        needs_rag: boolean;
        needs_tools: boolean;
        needs_memory: boolean;
        is_casual: boolean;
        latency_ms: number;
    };
    routing: {
        handler: string;
        routing_confidence: number;
        latency_ms: number;
        reasoning: string;
    };
}

export interface DocumentService {
    getAllDocuments(): Promise<unknown>;
    getDocumentChunks(docId: string, limit?: number): Promise<unknown>;
    uploadDocument(userId: string, filePath: string, fileName: string): Promise<unknown>;
    [key: string]: unknown;
}

