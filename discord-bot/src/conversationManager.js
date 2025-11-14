const fs = require('fs');
const path = require('path');

class ConversationManager {
    constructor() {
        this.conversationsPath = path.join(__dirname, '..', 'data', 'conversations');
        this.ensureDataDirectory();
    }

    ensureDataDirectory() {
        if (!fs.existsSync(this.conversationsPath)) {
            fs.mkdirSync(this.conversationsPath, { recursive: true });
        }
    }

    /**
     * Get conversation file path for a user
     */
    getUserFilePath(userId) {
        return path.join(this.conversationsPath, `${userId}.json`);
    }

    /**
     * Get conversation history for a user
     * @param {string} userId - Discord user ID
     * @returns {Promise<Array>} Conversation history
     */
    async getConversation(userId) {
        const filePath = this.getUserFilePath(userId);
        
        if (!fs.existsSync(filePath)) {
            return [];
        }

        try {
            const data = fs.readFileSync(filePath, 'utf8');
            const conversation = JSON.parse(data);
            return conversation.messages || [];
        } catch (error) {
            console.error(`Error reading conversation for ${userId}:`, error);
            return [];
        }
    }

    /**
     * Add a message to user's conversation history
     * @param {string} userId - Discord user ID
     * @param {string} question - User's question
     * @param {string} answer - Bot's answer
     */
    async addMessage(userId, question, answer) {
        const filePath = this.getUserFilePath(userId);
        const conversation = await this.getConversation(userId);
        
        conversation.push({
            question,
            answer,
            timestamp: new Date().toISOString()
        });

        // Keep only last 50 messages to avoid file bloat
        const recentMessages = conversation.slice(-50);

        const conversationData = {
            userId,
            messages: recentMessages,
            lastUpdated: new Date().toISOString()
        };

        try {
            fs.writeFileSync(filePath, JSON.stringify(conversationData, null, 2));
        } catch (error) {
            console.error(`Error saving conversation for ${userId}:`, error);
        }
    }

    /**
     * Clear conversation history for a user
     * @param {string} userId - Discord user ID
     */
    async clearConversation(userId) {
        const filePath = this.getUserFilePath(userId);
        if (fs.existsSync(filePath)) {
            fs.unlinkSync(filePath);
        }
    }

    /**
     * Get conversation summary (for context)
     * @param {string} userId - Discord user ID
     * @param {number} maxMessages - Maximum messages to include
     * @returns {Promise<Array>} Recent conversation messages
     */
    async getRecentConversation(userId, maxMessages = 5) {
        const conversation = await this.getConversation(userId);
        return conversation.slice(-maxMessages);
    }
}

module.exports = ConversationManager;

