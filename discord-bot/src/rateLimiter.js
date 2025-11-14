/**
 * Rate limiter for Discord bot commands and messages
 */
class RateLimiter {
    constructor() {
        // Store rate limit data: { userId: { count: number, resetTime: number } }
        this.rateLimits = new Map();
        
        // Configuration
        this.config = {
            // Per-user rate limits
            user: {
                commands: { max: 10, window: 60000 }, // 10 commands per minute
                messages: { max: 20, window: 60000 },  // 20 messages per minute
                uploads: { max: 3, window: 300000 }     // 3 uploads per 5 minutes
            },
            // Per-channel rate limits
            channel: {
                responses: { max: 30, window: 60000 }   // 30 responses per minute per channel
            }
        };
    }
    
    /**
     * Check if action is allowed for user
     * @param {string} userId - Discord user ID
     * @param {string} type - Type of action: 'commands', 'messages', 'uploads'
     * @returns {boolean} - True if allowed, false if rate limited
     */
    checkUserLimit(userId, type) {
        const limit = this.config.user[type];
        if (!limit) return true; // No limit configured
        
        const now = Date.now();
        const userData = this.rateLimits.get(userId) || {};
        const actionData = userData[type] || { count: 0, resetTime: now + limit.window };
        
        // Reset if window expired
        if (now > actionData.resetTime) {
            actionData.count = 0;
            actionData.resetTime = now + limit.window;
        }
        
        // Check limit
        if (actionData.count >= limit.max) {
            return false;
        }
        
        // Increment count
        actionData.count++;
        userData[type] = actionData;
        this.rateLimits.set(userId, userData);
        
        return true;
    }
    
    /**
     * Get remaining requests for user
     * @param {string} userId - Discord user ID
     * @param {string} type - Type of action
     * @returns {number} - Remaining requests
     */
    getRemaining(userId, type) {
        const limit = this.config.user[type];
        if (!limit) return Infinity;
        
        const now = Date.now();
        const userData = this.rateLimits.get(userId) || {};
        const actionData = userData[type] || { count: 0, resetTime: now + limit.window };
        
        if (now > actionData.resetTime) {
            return limit.max;
        }
        
        return Math.max(0, limit.max - actionData.count);
    }
    
    /**
     * Get reset time for user action
     * @param {string} userId - Discord user ID
     * @param {string} type - Type of action
     * @returns {number} - Timestamp when limit resets
     */
    getResetTime(userId, type) {
        const userData = this.rateLimits.get(userId) || {};
        const actionData = userData[type];
        return actionData ? actionData.resetTime : Date.now();
    }
    
    /**
     * Clean up old rate limit data (call periodically)
     */
    cleanup() {
        const now = Date.now();
        for (const [userId, userData] of this.rateLimits.entries()) {
            let hasActiveLimits = false;
            for (const [type, actionData] of Object.entries(userData)) {
                if (now < actionData.resetTime) {
                    hasActiveLimits = true;
                    break;
                }
            }
            if (!hasActiveLimits) {
                this.rateLimits.delete(userId);
            }
        }
    }
}

// Singleton instance
const rateLimiter = new RateLimiter();

// Cleanup every 5 minutes
setInterval(() => rateLimiter.cleanup(), 5 * 60 * 1000);

module.exports = rateLimiter;

