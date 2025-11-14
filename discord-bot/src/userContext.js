/**
 * User context manager for better user recognition and personalization
 */
class UserContext {
    constructor() {
        // Cache user contexts: { userId: { preferences, history, etc. } }
        this.userContexts = new Map();
        this.cacheTimeout = 30 * 60 * 1000; // 30 minutes
    }
    
    /**
     * Get or create user context
     * @param {string} userId - Discord user ID
     * @param {string} username - Discord username
     * @param {string} channelId - Channel ID
     * @returns {Object} - User context
     */
    async getUserContext(userId, username = null, channelId = null) {
        const cacheKey = `${userId}_${channelId || 'global'}`;
        
        // Check cache
        if (this.userContexts.has(cacheKey)) {
            const cached = this.userContexts.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.context;
            }
        }
        
        // Build context
        const context = {
            userId,
            username: username || 'Unknown',
            channelId,
            preferences: {
                responseStyle: 'balanced', // 'concise', 'detailed', 'balanced'
                useMemory: true,
                useDocuments: true
            },
            interactionHistory: {
                totalQueries: 0,
                lastQueryTime: null,
                favoriteTopics: [],
                documentInterests: []
            },
            metadata: {
                firstSeen: Date.now(),
                lastSeen: Date.now()
            }
        };
        
        // Cache context
        this.userContexts.set(cacheKey, {
            context,
            timestamp: Date.now()
        });
        
        return context;
    }
    
    /**
     * Update user context after interaction
     * @param {string} userId - Discord user ID
     * @param {string} channelId - Channel ID
     * @param {Object} update - Updates to apply
     */
    updateUserContext(userId, channelId, update) {
        const cacheKey = `${userId}_${channelId || 'global'}`;
        
        if (this.userContexts.has(cacheKey)) {
            const cached = this.userContexts.get(cacheKey);
            Object.assign(cached.context, update);
            cached.context.metadata.lastSeen = Date.now();
        }
    }
    
    /**
     * Extract user preferences from message patterns
     * @param {string} userId - Discord user ID
     * @param {string} message - User message
     * @param {Object} response - Bot response
     */
    async learnFromInteraction(userId, channelId, message, response) {
        const context = await this.getUserContext(userId, null, channelId);
        
        // Update interaction history
        context.interactionHistory.totalQueries++;
        context.interactionHistory.lastQueryTime = Date.now();
        
        // Detect preferences
        if (message.toLowerCase().includes('brief') || message.toLowerCase().includes('short')) {
            context.preferences.responseStyle = 'concise';
        } else if (message.toLowerCase().includes('detailed') || message.toLowerCase().includes('explain')) {
            context.preferences.responseStyle = 'detailed';
        }
        
        // Extract topics (simple keyword extraction)
        const keywords = this.extractKeywords(message);
        if (keywords.length > 0) {
            keywords.forEach(keyword => {
                if (!context.interactionHistory.favoriteTopics.includes(keyword)) {
                    context.interactionHistory.favoriteTopics.push(keyword);
                    // Keep only top 10
                    if (context.interactionHistory.favoriteTopics.length > 10) {
                        context.interactionHistory.favoriteTopics.shift();
                    }
                }
            });
        }
        
        this.updateUserContext(userId, channelId, context);
    }
    
    /**
     * Extract keywords from message
     * @param {string} message - User message
     * @returns {Array<string>} - Extracted keywords
     */
    extractKeywords(message) {
        // Simple keyword extraction (can be enhanced)
        const stopWords = new Set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'what', 'which', 'who', 'when', 'where', 'why', 'how']);
        
        const words = message.toLowerCase()
            .replace(/[^\w\s]/g, ' ')
            .split(/\s+/)
            .filter(word => word.length > 3 && !stopWords.has(word));
        
        // Return unique keywords
        return [...new Set(words)].slice(0, 5);
    }
    
    /**
     * Get personalized prompt additions based on user context
     * @param {string} userId - Discord user ID
     * @param {string} channelId - Channel ID
     * @returns {string} - Additional prompt context
     */
    getPersonalizedPrompt(userId, channelId) {
        const context = this.userContexts.get(`${userId}_${channelId || 'global'}`);
        if (!context) return '';
        
        const parts = [];
        
        if (context.preferences.responseStyle === 'concise') {
            parts.push('User prefers concise answers.');
        } else if (context.preferences.responseStyle === 'detailed') {
            parts.push('User prefers detailed explanations.');
        }
        
        if (context.interactionHistory.favoriteTopics.length > 0) {
            parts.push(`User frequently asks about: ${context.interactionHistory.favoriteTopics.slice(0, 3).join(', ')}.`);
        }
        
        return parts.length > 0 ? `[User Context: ${parts.join(' ')}]` : '';
    }
    
    /**
     * Clean up old contexts
     */
    cleanup() {
        const now = Date.now();
        for (const [key, cached] of this.userContexts.entries()) {
            if (now - cached.timestamp > this.cacheTimeout * 2) {
                this.userContexts.delete(key);
            }
        }
    }
}

// Singleton instance
const userContext = new UserContext();

// Cleanup every 10 minutes
setInterval(() => userContext.cleanup(), 10 * 60 * 1000);

module.exports = userContext;

