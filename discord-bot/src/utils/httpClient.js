/**
 * Modern HTTP Client using native fetch API with AbortController
 * Replaces native http module and axios for better performance and modern patterns
 * 
 * Features:
 * - Native fetch (Node.js 18+)
 * - AbortController for cancellable requests
 * - Automatic timeout handling
 * - Better error handling
 * - Streaming support
 * 
 * Compatible with CommonJS (can be imported with require)
 */

/**
 * Create a timeout signal for fetch requests
 * @param {number} timeoutMs - Timeout in milliseconds
 * @returns {AbortSignal} Signal that aborts after timeout
 */
function createTimeoutSignal(timeoutMs) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    
    // Clean up timeout when signal is aborted
    controller.signal.addEventListener('abort', () => clearTimeout(timeout));
    
    return controller.signal;
}

/**
 * Create a combined abort signal from multiple signals
 * @param {...AbortSignal} signals - Signals to combine
 * @returns {AbortSignal} Combined signal
 */
function combineSignals(...signals) {
    const controller = new AbortController();
    
    const abort = () => controller.abort();
    signals.forEach(signal => {
        if (signal.aborted) {
            abort();
        } else {
            signal.addEventListener('abort', abort);
        }
    });
    
    return controller.signal;
}

/**
 * Modern HTTP client with timeout and error handling
 * @param {string} url - Request URL
 * @param {Object} options - Fetch options
 * @param {number} options.timeout - Timeout in milliseconds (default: 30000)
 * @param {AbortSignal} options.signal - Optional abort signal
 * @param {Object} options.headers - Request headers
 * @param {string} options.method - HTTP method
 * @param {Object|string} options.body - Request body
 * @returns {Promise<Response>} Fetch response
 */
async function fetchWithTimeout(url, options = {}) {
    const {
        timeout = 30000,
        signal: userSignal,
        ...fetchOptions
    } = options;
    
    // Create timeout signal
    const timeoutSignal = createTimeoutSignal(timeout);
    
    // Combine signals if user provided one
    const signal = userSignal 
        ? combineSignals(timeoutSignal, userSignal)
        : timeoutSignal;
    
    try {
        const response = await fetch(url, {
            ...fetchOptions,
            signal
        });
        
        // Check for HTTP errors
        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new HTTPError(
                `HTTP ${response.status}: ${response.statusText}`,
                response.status,
                response.statusText,
                errorText
            );
        }
        
        return response;
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new TimeoutError(`Request timeout after ${timeout}ms`, timeout);
        }
        if (error instanceof HTTPError) {
            throw error;
        }
        throw new NetworkError(`Network request failed: ${error.message}`, error);
    }
}

/**
 * Fetch JSON with automatic parsing and error handling
 * @param {string} url - Request URL
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} Parsed JSON response
 */
async function fetchJSON(url, options = {}) {
    const response = await fetchWithTimeout(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    });
    
    try {
        return await response.json();
    } catch (error) {
        const text = await response.text().catch(() => '');
        throw new ParseError(
            `Failed to parse JSON response: ${error.message}`,
            text,
            error
        );
    }
}

/**
 * POST JSON data
 * @param {string} url - Request URL
 * @param {Object} data - Data to send
 * @param {Object} options - Additional fetch options
 * @returns {Promise<Object>} Parsed JSON response
 */
async function postJSON(url, data, options = {}) {
    return fetchJSON(url, {
        ...options,
        method: 'POST',
        body: JSON.stringify(data)
    });
}

/**
 * Custom error classes for better error handling
 */
class HTTPError extends Error {
    constructor(message, status, statusText, body) {
        super(message);
        this.name = 'HTTPError';
        this.status = status;
        this.statusText = statusText;
        this.body = body;
    }
}

class TimeoutError extends Error {
    constructor(message, timeout) {
        super(message);
        this.name = 'TimeoutError';
        this.timeout = timeout;
    }
}

class NetworkError extends Error {
    constructor(message, cause) {
        super(message);
        this.name = 'NetworkError';
        this.cause = cause;
    }
}

class ParseError extends Error {
    constructor(message, rawData, cause) {
        super(message);
        this.name = 'ParseError';
        this.rawData = rawData;
        this.cause = cause;
    }
}

/**
 * Check if error is retryable
 * @param {Error} error - Error to check
 * @returns {boolean} True if error is retryable
 */
function isRetryableError(error) {
    if (error instanceof TimeoutError) return true;
    if (error instanceof NetworkError) return true;
    if (error instanceof HTTPError) {
        // Retry on 5xx errors and specific 4xx errors
        return error.status >= 500 || error.status === 408 || error.status === 429;
    }
    return false;
}

// CommonJS export
module.exports = {
    createTimeoutSignal,
    combineSignals,
    fetchWithTimeout,
    fetchJSON,
    postJSON,
    HTTPError,
    TimeoutError,
    NetworkError,
    ParseError,
    isRetryableError
};

