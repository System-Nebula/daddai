/**
 * Type declarations for gopherAgent.js
 */
export interface RouteMessageContext {
    hasAttachments?: boolean;
    has_attachments?: boolean;
    isMentioned?: boolean;
    is_mentioned?: boolean;
    userId?: string;
    channelId?: string;
    guildId?: string;
    username?: string;
    recentMessages?: Array<{ role?: string; author?: string; content: string }>;
    [key: string]: unknown;
}

export interface RoutingResult {
    handler: string;
    intent?: {
        intent: string;
        should_respond?: boolean;
        needs_rag?: boolean;
        needs_tools?: boolean;
        needs_memory?: boolean;
        is_casual?: boolean;
        confidence?: number;
    };
    routing_confidence?: number;
    fast_path?: boolean;
    fallback?: boolean;
}

export interface GopherAgent {
    routeMessage(message: string, context?: RouteMessageContext): Promise<RoutingResult>;
    classifyIntent(message: string, context?: RouteMessageContext, useCache?: boolean): Promise<unknown>;
}

declare const gopherAgent: GopherAgent;
export default gopherAgent;

