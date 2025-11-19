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
 */

/**
 * Create a timeout signal for fetch requests
 * @param timeoutMs - Timeout in milliseconds
 * @returns Signal that aborts after timeout
 */
export function createTimeoutSignal(timeoutMs: number): AbortSignal {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    
    // Clean up timeout when signal is aborted
    controller.signal.addEventListener('abort', () => clearTimeout(timeout));
    
    return controller.signal;
}

/**
 * Create a combined abort signal from multiple signals
 * @param signals - Signals to combine
 * @returns Combined signal
 */
export function combineSignals(...signals: AbortSignal[]): AbortSignal {
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

export interface FetchOptions extends RequestInit {
    timeout?: number;
    signal?: AbortSignal;
}

/**
 * Modern HTTP client with timeout and error handling
 * @param url - Request URL
 * @param options - Fetch options
 * @returns Fetch response
 */
export async function fetchWithTimeout(url: string, options: FetchOptions = {}): Promise<Response> {
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
        if (error instanceof Error && error.name === 'AbortError') {
            throw new TimeoutError(`Request timeout after ${timeout}ms`, timeout);
        }
        if (error instanceof HTTPError) {
            throw error;
        }
        throw new NetworkError(`Network request failed: ${error instanceof Error ? error.message : String(error)}`, error as Error);
    }
}

/**
 * Fetch JSON with automatic parsing and error handling
 * @param url - Request URL
 * @param options - Fetch options
 * @returns Parsed JSON response
 */
export async function fetchJSON<T = unknown>(url: string, options: FetchOptions = {}): Promise<T> {
    const response = await fetchWithTimeout(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    });
    
    try {
        return await response.json() as T;
    } catch (error) {
        const text = await response.text().catch(() => '');
        throw new ParseError(
            `Failed to parse JSON response: ${error instanceof Error ? error.message : String(error)}`,
            text,
            error as Error
        );
    }
}

/**
 * POST JSON data
 * @param url - Request URL
 * @param data - Data to send
 * @param options - Additional fetch options
 * @returns Parsed JSON response
 */
export async function postJSON<T = unknown>(url: string, data: unknown, options: FetchOptions = {}): Promise<T> {
    return fetchJSON<T>(url, {
        ...options,
        method: 'POST',
        body: JSON.stringify(data)
    });
}

/**
 * Custom error classes for better error handling
 */
export class HTTPError extends Error {
    status: number;
    statusText: string;
    body: string;

    constructor(message: string, status: number, statusText: string, body: string) {
        super(message);
        this.name = 'HTTPError';
        this.status = status;
        this.statusText = statusText;
        this.body = body;
    }
}

export class TimeoutError extends Error {
    timeout: number;

    constructor(message: string, timeout: number) {
        super(message);
        this.name = 'TimeoutError';
        this.timeout = timeout;
    }
}

export class NetworkError extends Error {
    cause: Error;

    constructor(message: string, cause: Error) {
        super(message);
        this.name = 'NetworkError';
        this.cause = cause;
    }
}

export class ParseError extends Error {
    rawData: string;
    cause: Error;

    constructor(message: string, rawData: string, cause: Error) {
        super(message);
        this.name = 'ParseError';
        this.rawData = rawData;
        this.cause = cause;
    }
}

/**
 * Check if error is retryable
 * @param error - Error to check
 * @returns True if error is retryable
 */
export function isRetryableError(error: unknown): boolean {
    if (error instanceof TimeoutError) return true;
    if (error instanceof NetworkError) return true;
    if (error instanceof HTTPError) {
        // Retry on 5xx errors and specific 4xx errors
        return error.status >= 500 || error.status === 408 || error.status === 429;
    }
    return false;
}

