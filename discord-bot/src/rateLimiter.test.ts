import { describe, it } from 'node:test';
import assert from 'node:assert';
import rateLimiter from './rateLimiter.js';

describe('RateLimiter', () => {
    it('should allow requests within limit', () => {
        const userId = 'test-user-1';
        assert.strictEqual(rateLimiter.checkUserLimit(userId, 'commands'), true);
        assert.strictEqual(rateLimiter.checkUserLimit(userId, 'commands'), true);
    });

    it('should enforce rate limits', () => {
        const userId = 'test-user-2';
        // Make 10 requests (the limit)
        for (let i = 0; i < 10; i++) {
            rateLimiter.checkUserLimit(userId, 'commands');
        }
        // 11th request should be blocked
        assert.strictEqual(rateLimiter.checkUserLimit(userId, 'commands'), false);
    });

    it('should return remaining requests', () => {
        const userId = 'test-user-3';
        rateLimiter.checkUserLimit(userId, 'messages');
        const remaining = rateLimiter.getRemaining(userId, 'messages');
        assert.strictEqual(remaining, 19); // 20 - 1 = 19
    });

    it('should return reset time', () => {
        const userId = 'test-user-4';
        rateLimiter.checkUserLimit(userId, 'uploads');
        const resetTime = rateLimiter.getResetTime(userId, 'uploads');
        assert.ok(resetTime > Date.now());
    });
});

