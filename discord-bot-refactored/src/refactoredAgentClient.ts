/**
 * HTTP client for Refactored Agent Server.
 * Connects to the refactored agent HTTP server for message routing and agentic tasks.
 */
import * as http from 'http';
import * as https from 'https';
import { URL } from 'url';
import logger from './logger.js';

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
    };
    routing_confidence?: number;
    fallback?: boolean;
}

export interface AgenticTaskResult {
    status: string;
    result?: string;
    error?: string;
    tool_calls?: unknown[];
    steps?: unknown[];
}

class RefactoredAgentClient {
    private host: string;
    private port: number;
    private timeout: number;
    private useHttps: boolean;

    constructor() {
        this.host = process.env.REFACTORED_AGENT_HOST || 'localhost';
        this.port = parseInt(process.env.REFACTORED_AGENT_PORT || '8766', 10);
        // Longer timeout for agentic tasks (can take 60+ seconds)
        this.timeout = parseInt(process.env.REFACTORED_AGENT_TIMEOUT || '120000', 10); // 120 seconds default
        this.useHttps = process.env.REFACTORED_AGENT_HTTPS === 'true';
    }

    /**
     * Route a message to determine the appropriate handler
     */
    async routeMessage(message: string, context: RouteMessageContext = {}): Promise<RoutingResult> {
        return this._makeRequest('/route_message', {
            message,
            context
        }) as Promise<RoutingResult>;
    }

    /**
     * Run an agentic task using the ReAct agent
     */
    async runAgenticTask(message: string, context: RouteMessageContext = {}): Promise<AgenticTaskResult> {
        // Use longer timeout for agentic tasks (can take 2+ minutes for complex tasks)
        const originalTimeout = this.timeout;
        this.timeout = parseInt(process.env.REFACTORED_AGENT_AGENTIC_TIMEOUT || '180000', 10); // 3 minutes for agentic tasks
        try {
            return await this._makeRequest('/run_agentic_task', {
                message,
                context
            }) as Promise<AgenticTaskResult>;
        } finally {
            this.timeout = originalTimeout;
        }
    }

    /**
     * Check if agentic mode should be used
     */
    async shouldUseAgenticMode(message: string, intentResult?: RoutingResult | null): Promise<boolean> {
        const result = await this._makeRequest('/should_use_agentic_mode', {
            message,
            intent_result: intentResult || null
        }) as { should_use: boolean };
        return result.should_use;
    }

    /**
     * Health check
     */
    async healthCheck(): Promise<boolean> {
        try {
            const result = await this._makeRequest('/health', {}, 'GET');
            return (result as { status: string }).status === 'ok';
        } catch {
            return false;
        }
    }

    /**
     * Make HTTP request to the refactored agent server
     */
    private _makeRequest(path: string, data: unknown, method: string = 'POST'): Promise<unknown> {
        return new Promise((resolve, reject) => {
            const postData = method === 'POST' ? JSON.stringify(data) : undefined;
            const url = new URL(path, `${this.useHttps ? 'https' : 'http'}://${this.host}:${this.port}`);

            const options: http.RequestOptions = {
                hostname: url.hostname,
                port: url.port || (this.useHttps ? 443 : 80),
                path: url.pathname,
                method,
                headers: {
                    'Content-Type': 'application/json',
                    ...(postData ? { 'Content-Length': Buffer.byteLength(postData) } : {})
                },
                timeout: this.timeout
            };

            const requestModule = this.useHttps ? https : http;

            const req = requestModule.request(options, (res) => {
                let responseData = '';

                res.on('data', (chunk) => {
                    responseData += chunk;
                });

                res.on('end', () => {
                    if (res.statusCode !== 200) {
                        try {
                            const error = JSON.parse(responseData);
                            reject(new Error(error.error || `HTTP ${res.statusCode}: ${responseData}`));
                        } catch {
                            reject(new Error(`HTTP ${res.statusCode}: ${responseData}`));
                        }
                        return;
                    }

                    try {
                        const result = JSON.parse(responseData);
                        resolve(result);
                    } catch (error) {
                        const err = error as Error;
                        reject(new Error(`Failed to parse response: ${err.message}`));
                    }
                });
            });

            req.on('error', (error) => {
                logger.error(`Refactored Agent HTTP request failed: ${error.message}`);
                reject(new Error(`HTTP request failed: ${error.message}`));
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Refactored Agent HTTP request timeout'));
            });

            if (postData) {
                req.write(postData);
            }
            req.end();
        });
    }
}

// Export singleton instance
const refactoredAgentClient = new RefactoredAgentClient();
export default refactoredAgentClient;

