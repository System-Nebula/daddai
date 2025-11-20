/**
 * Express middleware for OpenTelemetry observability
 * Adds tracing, metrics, and logging to HTTP requests
 */

const { withSpan, addSpanAttributes, addSpanEvent, getTraceContext } = require('../utils/observability');
const { asyncHandler } = require('../utils/errorHandler');
const logger = require('../logger');

/**
 * Request tracing middleware
 * Creates spans for HTTP requests and adds trace context to logs
 */
function tracingMiddleware(req, res, next) {
    const startTime = Date.now();
    const { method, path, url } = req;

    return withSpan(
        `HTTP ${method} ${path}`,
        async (span) => {
            // Add request attributes
            addSpanAttributes({
                'http.method': method,
                'http.url': url,
                'http.route': path,
                'http.user_agent': req.get('user-agent') || '',
                'http.request_id': req.headers['x-request-id'] || '',
            });

            // Add trace context to request for logging
            const traceContext = getTraceContext();
            req.traceContext = traceContext;

            // Log request start with trace context
            logger.info('HTTP Request started', {
                ...traceContext,
                method,
                path,
                ip: req.ip,
            });

            // Track response
            res.on('finish', () => {
                const duration = Date.now() - startTime;
                const statusCode = res.statusCode;

                // Add response attributes
                addSpanAttributes({
                    'http.status_code': statusCode,
                    'http.response_size': res.get('content-length') || 0,
                });

                // Add event for response
                addSpanEvent('http.response', {
                    statusCode,
                    duration,
                });

                // Log request completion
                const logLevel = statusCode >= 400 ? 'warn' : 'info';
                logger[logLevel]('HTTP Request completed', {
                    ...traceContext,
                    method,
                    path,
                    statusCode,
                    duration: `${duration}ms`,
                });
            });

            next();
        },
        {
            kind: 1, // SERVER
        }
    );
}

/**
 * Error tracking middleware
 * Records errors in spans and logs
 */
function errorTrackingMiddleware(err, req, res, next) {
    const traceContext = getTraceContext();

    // Log error with trace context
    logger.error('HTTP Request error', {
        ...traceContext,
        error: {
            message: err.message,
            stack: err.stack,
            name: err.name,
        },
        method: req.method,
        path: req.path,
    });

    next(err);
}

/**
 * Metrics middleware
 * Tracks request metrics (can be combined with existing metrics)
 */
function metricsMiddleware(req, res, next) {
    const startTime = Date.now();

    res.on('finish', () => {
        const duration = Date.now() - startTime;
        const { method, path } = req;
        const statusCode = res.statusCode;

        // Record metrics (integrate with existing metrics collector if needed)
        // This is a placeholder - you can integrate with your existing metrics.js
        addSpanEvent('http.metrics', {
            duration,
            statusCode,
            method,
            path,
        });
    });

    next();
}

/**
 * Combined observability middleware
 * Combines tracing, metrics, and error tracking
 */
const observabilityMiddleware = [
    tracingMiddleware,
    metricsMiddleware,
    // Error tracking is handled by error handler middleware
];

module.exports = {
    tracingMiddleware,
    errorTrackingMiddleware,
    metricsMiddleware,
    observabilityMiddleware,
};

