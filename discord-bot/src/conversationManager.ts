/**
 * Conversation Manager using Neo4j via RAG server.
 * Stores conversations in Neo4j instead of local files.
 */

import type PersistentRAGService from './ragServicePersistent';

interface ConversationMessage {
    role?: string;
    content?: string;
    [key: string]: unknown;
}

interface ConversationResponse {
    error?: string;
    result?: {
        messages?: ConversationMessage[];
    };
}

class ConversationManager {
    private ragService: PersistentRAGService | null;

    constructor(ragService: PersistentRAGService | null = null) {
        this.ragService = ragService;
    }

    /**
     * Set the RAG service for conversation storage
     * @param ragService - RAG service instance
     */
    setRAGService(ragService: PersistentRAGService): void {
        this.ragService = ragService;
    }

    /**
     * Get conversation history for a user from Neo4j
     * @param userId - Discord user ID
     * @returns Conversation history
     */
    async getConversation(userId: string): Promise<ConversationMessage[]> {
        if (!this.ragService) {
            console.warn('RAG service not available, returning empty conversation');
            return [];
        }

        try {
            const response = await this.ragService.sendConversationRequest({
                method: 'get_conversation',
                params: {
                    user_id: userId,
                    limit: 50
                }
            }) as ConversationResponse;
            
            if (response.error) {
                console.error(`Error getting conversation for ${userId}:`, response.error);
                return [];
            }
            
            return response.result?.messages || [];
        } catch (error) {
            console.error(`Error getting conversation for ${userId}:`, error);
            return [];
        }
    }

    /**
     * Add a message to user's conversation history in Neo4j
     * @param userId - Discord user ID
     * @param question - User's question
     * @param answer - Bot's answer
     * @param channelId - Optional Discord channel ID
     */
    async addMessage(userId: string, question: string, answer: string, channelId: string | null = null): Promise<void> {
        if (!this.ragService) {
            console.warn('RAG service not available, cannot save conversation');
            return;
        }

        try {
            await this.ragService.sendConversationRequest({
                method: 'add_conversation',
                params: {
                    user_id: userId,
                    question: question,
                    answer: answer,
                    channel_id: channelId
                }
            });
        } catch (error) {
            console.error(`Error saving conversation for ${userId}:`, error);
        }
    }

    /**
     * Clear conversation history for a user in Neo4j
     * @param userId - Discord user ID
     */
    async clearConversation(userId: string): Promise<void> {
        if (!this.ragService) {
            console.warn('RAG service not available, cannot clear conversation');
            return;
        }

        try {
            await this.ragService.sendConversationRequest({
                method: 'clear_conversation',
                params: {
                    user_id: userId
                }
            });
        } catch (error) {
            console.error(`Error clearing conversation for ${userId}:`, error);
        }
    }

    /**
     * Get conversation summary (for context) from Neo4j
     * @param userId - Discord user ID
     * @param maxMessages - Maximum messages to include
     * @returns Recent conversation messages
     */
    async getRecentConversation(userId: string, maxMessages: number = 5): Promise<ConversationMessage[]> {
        if (!this.ragService) {
            console.warn('RAG service not available, returning empty conversation');
            return [];
        }

        try {
            const response = await this.ragService.sendConversationRequest({
                method: 'get_recent_conversation',
                params: {
                    user_id: userId,
                    max_messages: maxMessages
                }
            }) as ConversationResponse;
            
            if (response.error) {
                console.error(`Error getting recent conversation for ${userId}:`, response.error);
                return [];
            }
            
            return response.result?.messages || [];
        } catch (error) {
            console.error(`Error getting recent conversation for ${userId}:`, error);
            return [];
        }
    }

    /**
     * Get semantically relevant conversations for a user based on current query
     * Uses vector similarity to find conversations related to what the user is asking
     * @param userId - Discord user ID
     * @param query - Current user query
     * @param topK - Number of relevant conversations to retrieve
     * @returns Relevant conversation messages
     */
    async getRelevantConversations(userId: string, query: string, topK: number = 5): Promise<ConversationMessage[]> {
        if (!this.ragService) {
            console.warn('RAG service not available, returning empty conversation');
            return [];
        }

        try {
            const response = await this.ragService.sendConversationRequest({
                method: 'get_relevant_conversations',
                params: {
                    user_id: userId,
                    query: query,
                    top_k: topK
                }
            }) as ConversationResponse;
            
            if (response.error) {
                console.error(`Error getting relevant conversations for ${userId}:`, response.error);
                // Fallback to recent conversations
                return this.getRecentConversation(userId, topK);
            }
            
            return response.result?.messages || [];
        } catch (error) {
            console.error(`Error getting relevant conversations for ${userId}:`, error);
            // Fallback to recent conversations
            return this.getRecentConversation(userId, topK);
        }
    }
}

export default ConversationManager;

