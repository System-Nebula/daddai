/**
 * Example: Modernized HTTP client wrapper for Python services
 * This demonstrates how to use the new httpClient.js with modern patterns
 * 
 * Usage example:
 * const httpClient = require('./utils/modernHttpClient');
 * const response = await httpClient.postJSON('http://localhost:8767/chat', { message: 'Hello' });
 */

const { fetchJSON, postJSON, fetchWithTimeout, HTTPError, TimeoutError, NetworkError, isRetryableError } = require('./httpClient');
const logger = require('../logger');

/**
 * Modern HTTP client wrapper with retry logic and better error handling
 */
class ModernHttpClient {
    constructor(baseUrl, options = {}) {
        this.baseUrl = baseUrl;
        this.defaultTimeout = options.timeout || 30000;
        this.defaultRetries = options.retries || 3;
    }

    /**
     * Make a request with automatic retry on retryable errors
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Request options
     * @returns {Promise<Object>} Response data
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const timeout = options.timeout ?? this.defaultTimeout;
        const maxRetries = options.retries ?? this.defaultRetries;
        
        let lastError;
        
        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                const response = await fetchJSON(url, {
                    ...options,
                    timeout
                });
                
                logger.debug('[HTTP] Request successful', {
                    url,
                    attempt: attempt + 1,
                    status: 'success'
                });
                
                return response;
            } catch (error) {
                lastError = error;
                
                // Don't retry on non-retryable errors
                if (!isRetryableError(error) || attempt === maxRetries) {
                    throw error;
                }
                
                // Calculate backoff delay (exponential backoff with jitter)
                const delay = Math.min(1000 * Math.pow(2, attempt) + Math.random() * 1000, 10000);
                
                logger.warn('[HTTP] Request failed, retrying', {
                    url,
                    attempt: attempt + 1,
                    maxRetries,
                    delay,
                    error: error.message
                });
                
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
        
        throw lastError;
    }

    /**
     * POST JSON data
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Data to send
     * @param {Object} options - Request options
     * @returns {Promise<Object>} Response data
     */
    async post(endpoint, data, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * GET request
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Request options
     * @returns {Promise<Object>} Response data
     */
    async get(endpoint, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'GET'
        });
    }

    /**
     * Health check endpoint
     * @returns {Promise<boolean>} True if service is healthy
     */
    async healthCheck() {
        try {
            await this.get('/ping', { timeout: 5000 });
            return true;
        } catch (error) {
            logger.error('[HTTP] Health check failed', { error: error.message });
            return false;
        }
    }
}

module.exports = {
    ModernHttpClient,
    HTTPError,
    TimeoutError,
    NetworkError,
    isRetryableError
};

