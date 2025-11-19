/**
 * Tests for modern HTTP client using Node.js built-in test runner
 * Run with: npm test
 * Run with watch: npm run test:watch
 * 
 * Note: Node.js test runner supports both CommonJS and ES modules
 */

const { test, describe } = require('node:test');
const assert = require('node:assert');
const { fetchJSON, postJSON, HTTPError, TimeoutError, NetworkError, isRetryableError } = require('../src/utils/httpClient');

describe('HTTP Client', () => {
    describe('fetchJSON', () => {
        test('should fetch JSON successfully', async () => {
            // Mock fetch for testing
            const originalFetch = global.fetch;
            global.fetch = async (url, options) => {
                return {
                    ok: true,
                    json: async () => ({ success: true, data: 'test' }),
                    text: async () => JSON.stringify({ success: true, data: 'test' })
                };
            };

            try {
                const result = await fetchJSON('http://example.com/api');
                assert.strictEqual(result.success, true);
                assert.strictEqual(result.data, 'test');
            } finally {
                global.fetch = originalFetch;
            }
        });

        test('should handle HTTP errors', async () => {
            const originalFetch = global.fetch;
            global.fetch = async (url, options) => {
                return {
                    ok: false,
                    status: 404,
                    statusText: 'Not Found',
                    text: async () => JSON.stringify({ error: 'Not found' })
                };
            };

            try {
                await assert.rejects(
                    async () => await fetchJSON('http://example.com/api'),
                    HTTPError
                );
            } finally {
                global.fetch = originalFetch;
            }
        });

        test('should handle timeouts', async () => {
            const originalFetch = global.fetch;
            global.fetch = async (url, options) => {
                // Simulate timeout by aborting signal
                if (options.signal) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                    options.signal.abort();
                }
                throw new Error('AbortError');
            };

            try {
                await assert.rejects(
                    async () => await fetchJSON('http://example.com/api', { timeout: 50 }),
                    TimeoutError
                );
            } finally {
                global.fetch = originalFetch;
            }
        });
    });

    describe('isRetryableError', () => {
        test('should identify retryable errors', () => {
            assert.strictEqual(isRetryableError(new TimeoutError('Timeout', 5000)), true);
            assert.strictEqual(isRetryableError(new NetworkError('Network error')), true);
            assert.strictEqual(isRetryableError(new HTTPError('Server error', 500, 'Internal Server Error')), true);
            assert.strictEqual(isRetryableError(new HTTPError('Not found', 404, 'Not Found')), false);
        });
    });

    describe('postJSON', () => {
        test('should POST JSON data', async () => {
            const originalFetch = global.fetch;
            let capturedBody = null;

            global.fetch = async (url, options) => {
                capturedBody = options.body;
                return {
                    ok: true,
                    json: async () => ({ success: true }),
                    text: async () => JSON.stringify({ success: true })
                };
            };

            try {
                const data = { message: 'Hello', history: [] };
                await postJSON('http://example.com/api', data);
                assert.strictEqual(capturedBody, JSON.stringify(data));
            } finally {
                global.fetch = originalFetch;
            }
        });
    });
});

