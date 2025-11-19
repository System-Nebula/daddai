/**
 * Enhanced Logger with OpenTelemetry Integration
 * Extends existing logger with trace context and structured logging
 */

const winston = require('winston');
const path = require('path');
const { getTraceContext } = require('./observability');
const logger = require('../logger');

/**
 * Enhanced logger that automatically includes trace context
 */
class EnhancedLogger {
    constructor(baseLogger) {
        this.baseLogger = baseLogger;
    }

    /**
     * Add trace context to log metadata
     */
    _enrichMeta(meta = {}) {
        const traceContext = getTraceContext();
        return {
            ...traceContext,
            ...meta,
        };
    }

    /**
     * Log with trace context
     */
    log(level, message, meta = {}) {
        return this.baseLogger.log(level, message, this._enrichMeta(meta));
    }

    /**
     * Log error with trace context and stack trace
     */
    error(message, meta = {}) {
        return this.baseLogger.error(message, this._enrichMeta(meta));
    }

    /**
     * Log warning with trace context
     */
    warn(message, meta = {}) {
        return this.baseLogger.warn(message, this._enrichMeta(meta));
    }

    /**
     * Log info with trace context
     */
    info(message, meta = {}) {
        return this.baseLogger.info(message, this._enrichMeta(meta));
    }

    /**
     * Log debug with trace context
     */
    debug(message, meta = {}) {
        return this.baseLogger.debug(message, this._enrichMeta(meta));
    }

    /**
     * Log service call with timing and trace context
     */
    logServiceCall(service, method, duration, success = true, error = null) {
        const meta = {
            service,
            method,
            duration: `${duration}ms`,
            success,
        };

        if (error) {
            meta.error = {
                message: error.message,
                code: error.code,
                name: error.name,
            };
        }

        const level = success ? 'debug' : 'warn';
        return this[level](`Service call: ${service}.${method}`, meta);
    }

    /**
     * Log HTTP request with trace context
     */
    logRequest(req, res, duration) {
        const meta = {
            method: req.method,
            path: req.path,
            statusCode: res.statusCode,
            duration: `${duration}ms`,
            userAgent: req.get('user-agent'),
            ip: req.ip,
        };

        const level = res.statusCode >= 400 ? 'warn' : 'info';
        return this[level](`HTTP ${req.method} ${req.path}`, meta);
    }

    /**
     * Log with span context (for OpenTelemetry spans)
     */
    logWithSpan(span, level, message, meta = {}) {
        const spanContext = span.spanContext();
        const enrichedMeta = {
            ...this._enrichMeta(meta),
            spanId: spanContext.spanId,
            traceId: spanContext.traceId,
        };
        return this.baseLogger.log(level, message, enrichedMeta);
    }
}

// Create enhanced logger instance
const enhancedLogger = new EnhancedLogger(logger);

module.exports = enhancedLogger;

