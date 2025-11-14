/**
 * Conversation Manager using Neo4j via RAG server.
 * Stores conversations in Neo4j instead of local files.
 */
class ConversationManager {
    constructor(ragService = null) {
        this.ragService = ragService;
    }

    /**
     * Set the RAG service for conversation storage
     * @param {Object} ragService - RAG service instance
     */
    setRAGService(ragService) {
        this.ragService = ragService;
    }

    /**
     * Get conversation history for a user from Neo4j
     * @param {string} userId - Discord user ID
     * @returns {Promise<Array>} Conversation history
     */
    async getConversation(userId) {
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
            });
            
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
     * @param {string} userId - Discord user ID
     * @param {string} question - User's question
     * @param {string} answer - Bot's answer
     * @param {string} channelId - Optional Discord channel ID
     */
    async addMessage(userId, question, answer, channelId = null) {
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
     * @param {string} userId - Discord user ID
     */
    async clearConversation(userId) {
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
     * @param {string} userId - Discord user ID
     * @param {number} maxMessages - Maximum messages to include
     * @returns {Promise<Array>} Recent conversation messages
     */
    async getRecentConversation(userId, maxMessages = 5) {
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
            });
            
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
     * @param {string} userId - Discord user ID
     * @param {string} query - Current user query
     * @param {number} topK - Number of relevant conversations to retrieve
     * @returns {Promise<Array>} Relevant conversation messages
     */
    async getRelevantConversations(userId, query, topK = 5) {
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
            });
            
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

module.exports = ConversationManager;

