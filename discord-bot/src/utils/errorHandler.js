/**
 * Modern error handling utilities
 * Provides structured error handling with proper error types and recovery strategies
 */

const logger = require('../logger');

/**
 * Base error class for application errors
 */
class AppError extends Error {
    constructor(message, code, statusCode = 500, context = {}) {
        super(message);
        this.name = this.constructor.name;
        this.code = code;
        this.statusCode = statusCode;
        this.context = context;
        this.timestamp = new Date().toISOString();
        Error.captureStackTrace(this, this.constructor);
    }

    toJSON() {
        return {
            name: this.name,
            message: this.message,
            code: this.code,
            statusCode: this.statusCode,
            context: this.context,
            timestamp: this.timestamp
        };
    }
}

/**
 * Service unavailable error
 */
class ServiceUnavailableError extends AppError {
    constructor(service, cause) {
        super(
            `Service unavailable: ${service}`,
            'SERVICE_UNAVAILABLE',
            503,
            { service, cause: cause?.message }
        );
        this.cause = cause;
    }
}

/**
 * Validation error
 */
class ValidationError extends AppError {
    constructor(message, field, value) {
        super(
            message || `Validation failed for field: ${field}`,
            'VALIDATION_ERROR',
            400,
            { field, value }
        );
    }
}

/**
 * Rate limit error
 */
class RateLimitError extends AppError {
    constructor(retryAfter) {
        super(
            'Rate limit exceeded',
            'RATE_LIMIT_EXCEEDED',
            429,
            { retryAfter }
        );
        this.retryAfter = retryAfter;
    }
}

/**
 * Error handler middleware for Express
 */
function errorHandler(err, req, res, next) {
    // Log error
    logger.error('Error occurred', {
        error: {
            name: err.name,
            message: err.message,
            stack: err.stack,
            code: err.code
        },
        request: {
            method: req.method,
            path: req.path,
            ip: req.ip
        }
    });

    // Determine status code
    const statusCode = err.statusCode || err.status || 500;
    
    // Don't leak error details in production
    const isDevelopment = process.env.NODE_ENV === 'development';
    
    // Format error response
    const errorResponse = {
        error: {
            message: err.message || 'Internal server error',
            code: err.code || 'INTERNAL_ERROR',
            ...(isDevelopment && { stack: err.stack }),
            ...(err.context && { context: err.context })
        },
        timestamp: new Date().toISOString()
    };

    res.status(statusCode).json(errorResponse);
}

/**
 * Async error wrapper for Express routes
 * Wraps async route handlers to automatically catch errors
 */
function asyncHandler(fn) {
    return (req, res, next) => {
        Promise.resolve(fn(req, res, next)).catch(next);
    };
}

/**
 * Handle unhandled promise rejections
 */
function setupUnhandledRejectionHandler() {
    process.on('unhandledRejection', (reason, promise) => {
        logger.error('Unhandled promise rejection', {
            reason: reason?.message || reason,
            stack: reason?.stack
        });
        
        // In production, you might want to gracefully shutdown
        if (process.env.NODE_ENV === 'production') {
            // Log and continue - don't crash the process
            // Consider implementing graceful shutdown logic here
        }
    });
}

/**
 * Handle uncaught exceptions
 */
function setupUncaughtExceptionHandler() {
    process.on('uncaughtException', (error) => {
        logger.error('Uncaught exception', {
            error: {
                message: error.message,
                stack: error.stack
            }
        });
        
        // In production, exit gracefully
        if (process.env.NODE_ENV === 'production') {
            // Give time for logs to flush
            setTimeout(() => {
                process.exit(1);
            }, 1000);
        }
    });
}

/**
 * Initialize error handlers
 */
function initializeErrorHandlers() {
    setupUnhandledRejectionHandler();
    setupUncaughtExceptionHandler();
}

module.exports = {
    AppError,
    ServiceUnavailableError,
    ValidationError,
    RateLimitError,
    errorHandler,
    asyncHandler,
    initializeErrorHandlers
};

