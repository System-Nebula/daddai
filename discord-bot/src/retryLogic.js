/**
 * Retry logic with exponential backoff for transient failures.
 * Supports configurable retry counts, backoff strategies, and error filtering.
 */
const logger = require('./logger');

/**
 * Default retry configuration
 */
const DEFAULT_CONFIG = {
    maxRetries: 3,
    initialDelay: 1000, // 1 second
    maxDelay: 30000, // 30 seconds
    factor: 2, // Exponential factor
    jitter: true, // Add random jitter to prevent thundering herd
    retryableErrors: [
        'timeout',
        'ECONNRESET',
        'ECONNREFUSED',
        'ETIMEDOUT',
        'ENOTFOUND',
        'EAI_AGAIN'
    ]
};

/**
 * Check if an error is retryable
 * @param {Error} error - Error to check
 * @param {Array<string>} retryableErrors - List of retryable error codes/messages
 * @returns {boolean} True if error is retryable
 */
function isRetryableError(error, retryableErrors = DEFAULT_CONFIG.retryableErrors) {
    if (!error) return false;
    
    const errorMessage = error.message?.toLowerCase() || '';
    const errorCode = error.code?.toLowerCase() || '';
    
    // Check if error message or code matches retryable patterns
    return retryableErrors.some(pattern => {
        const patternLower = pattern.toLowerCase();
        return errorMessage.includes(patternLower) || errorCode === patternLower;
    });
}

/**
 * Calculate delay with exponential backoff and optional jitter
 * @param {number} attempt - Current attempt number (0-indexed)
 * @param {Object} config - Retry configuration
 * @returns {number} Delay in milliseconds
 */
function calculateDelay(attempt, config = {}) {
    const {
        initialDelay = DEFAULT_CONFIG.initialDelay,
        maxDelay = DEFAULT_CONFIG.maxDelay,
        factor = DEFAULT_CONFIG.factor,
        jitter = DEFAULT_CONFIG.jitter
    } = config;
    
    // Exponential backoff: initialDelay * (factor ^ attempt)
    let delay = initialDelay * Math.pow(factor, attempt);
    
    // Cap at maxDelay
    delay = Math.min(delay, maxDelay);
    
    // Add jitter (random value between 0 and 10% of delay)
    if (jitter) {
        const jitterAmount = delay * 0.1 * Math.random();
        delay = delay + jitterAmount;
    }
    
    return Math.floor(delay);
}

/**
 * Sleep for specified milliseconds
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise<void>}
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Retry a function with exponential backoff
 * @param {Function} fn - Async function to retry
 * @param {Object} options - Retry options
 * @param {number} options.maxRetries - Maximum number of retries (default: 3)
 * @param {number} options.initialDelay - Initial delay in ms (default: 1000)
 * @param {number} options.maxDelay - Maximum delay in ms (default: 30000)
 * @param {number} options.factor - Exponential factor (default: 2)
 * @param {boolean} options.jitter - Add jitter to delays (default: true)
 * @param {Array<string>} options.retryableErrors - List of retryable error patterns
 * @param {Function} options.shouldRetry - Custom function to determine if error is retryable
 * @param {Function} options.onRetry - Callback called before each retry
 * @param {Object} context - Context for logging
 * @returns {Promise<any>} Result of the function
 */
async function retryWithBackoff(fn, options = {}, context = {}) {
    const config = {
        ...DEFAULT_CONFIG,
        ...options
    };
    
    let lastError;
    
    for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
        try {
            const result = await fn();
            
            if (attempt > 0) {
                logger.info('[Retry] Operation succeeded after retries', {
                    ...context,
                    attempt: attempt + 1,
                    totalAttempts: attempt + 1
                });
            }
            
            return result;
        } catch (error) {
            lastError = error;
            
            // Check if error is retryable
            const isRetryable = config.shouldRetry
                ? config.shouldRetry(error, attempt)
                : isRetryableError(error, config.retryableErrors);
            
            // Don't retry if not retryable or exceeded max retries
            if (!isRetryable || attempt >= config.maxRetries) {
                if (attempt > 0) {
                    logger.warn('[Retry] Operation failed after retries', {
                        ...context,
                        attempt: attempt + 1,
                        totalAttempts: attempt + 1,
                        error: error.message,
                        retryable: isRetryable
                    });
                }
                throw error;
            }
            
            // Calculate delay for next retry
            const delay = calculateDelay(attempt, config);
            
            logger.warn('[Retry] Operation failed, retrying', {
                ...context,
                attempt: attempt + 1,
                maxRetries: config.maxRetries,
                delay: `${delay}ms`,
                error: error.message
            });
            
            // Call onRetry callback if provided
            if (config.onRetry) {
                try {
                    await config.onRetry(error, attempt, delay);
                } catch (callbackError) {
                    logger.error('[Retry] onRetry callback failed', {
                        ...context,
                        error: callbackError.message
                    });
                }
            }
            
            // Wait before retrying
            await sleep(delay);
        }
    }
    
    // Should never reach here, but just in case
    throw lastError;
}

/**
 * Create a retry wrapper function
 * @param {Object} options - Retry configuration
 * @returns {Function} Wrapped function that automatically retries
 */
function createRetryWrapper(options = {}) {
    return async (fn, context = {}) => {
        return retryWithBackoff(fn, options, context);
    };
}

module.exports = {
    retryWithBackoff,
    createRetryWrapper,
    isRetryableError,
    calculateDelay,
    DEFAULT_CONFIG
};

