/**
 * Enhanced centralized logging system for Discord bot
 * Features: Structured logging, correlation IDs, proper log levels
 */
import winston from 'winston';
import path from 'path';
import crypto from 'crypto';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { AsyncLocalStorage } from 'async_hooks';

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Create logs directory if it doesn't exist
const logsDir = path.join(__dirname, '..', 'logs');
if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir, { recursive: true });
}

// Correlation ID storage (using AsyncLocalStorage for async context)
const correlationIdStorage = new AsyncLocalStorage<{ correlationId: string }>();

// Generate correlation ID
function generateCorrelationId(): string {
    // Use crypto.randomUUID() if available (Node 14.17.0+), otherwise fallback
    if (crypto.randomUUID) {
        return crypto.randomUUID();
    }
    // Fallback for older Node versions
    return crypto.randomBytes(16).toString('hex');
}

// Get current correlation ID
function getCorrelationId(): string | null {
    const store = correlationIdStorage.getStore();
    return store?.correlationId || null;
}

// Run function with correlation ID
function withCorrelationId<T>(correlationId: string, callback: () => T): T {
    return correlationIdStorage.run({ correlationId }, callback);
}

interface LogMeta {
    correlationId?: string;
    service?: string;
    error?: Error;
    errorMessage?: string;
    errorStack?: string;
    errorName?: string;
    [key: string]: unknown;
}

interface RequestLogMeta extends LogMeta {
    method: string;
    path: string;
    statusCode: number;
    duration: string;
    ip?: string;
    userAgent?: string;
}

interface ServiceCallLogMeta extends LogMeta {
    service: string;
    method: string;
    duration: string;
    success: boolean;
    error?: {
        message: string;
        code?: string;
    };
}

// Enhanced log format with correlation ID
const logFormat = winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.errors({ stack: true }),
    winston.format.splat(),
    winston.format((info) => {
        // Add correlation ID if available
        const correlationId = getCorrelationId();
        if (correlationId) {
            info.correlationId = correlationId;
        }
        
        // Ensure service name is set
        if (!info.service) {
            info.service = 'discord-bot';
        }
        
        // Extract error details if present
        if (info.error) {
            info.errorMessage = info.error.message;
            info.errorStack = info.error.stack;
            info.errorName = info.error.name;
        }
        
        return info;
    })(),
    winston.format.json()
);

// Console format (more readable with correlation ID)
const consoleFormat = winston.format.combine(
    winston.format.colorize(),
    winston.format.timestamp({ format: 'HH:mm:ss' }),
    winston.format.printf(({ timestamp, level, message, correlationId, ...meta }) => {
        let msg = `${timestamp} [${level}]`;
        
        // Add correlation ID if present
        if (correlationId) {
            msg += ` [${correlationId.substring(0, 8)}]`;
        }
        
        msg += `: ${message}`;
        
        // Add metadata (excluding internal fields)
        const filteredMeta = { ...meta };
        delete filteredMeta.service;
        delete filteredMeta.timestamp;
        delete filteredMeta.level;
        
        if (Object.keys(filteredMeta).length > 0) {
            // Format metadata nicely
            const metaStr = JSON.stringify(filteredMeta, null, 0);
            if (metaStr.length < 200) {
                msg += ` ${metaStr}`;
            } else {
                msg += ` ${metaStr.substring(0, 200)}...`;
            }
        }
        
        return msg;
    })
);

// Create logger instance
const logger = winston.createLogger({
    level: process.env.LOG_LEVEL || 'info',
    format: logFormat,
    defaultMeta: { service: 'discord-bot' },
    transports: [
        // Write all logs to console
        new winston.transports.Console({
            format: consoleFormat
        }),
        // Write all logs to combined.log
        new winston.transports.File({
            filename: path.join(logsDir, 'combined.log'),
            maxsize: 10485760, // 10MB
            maxFiles: 5,
            format: logFormat
        }),
        // Write errors to error.log
        new winston.transports.File({
            filename: path.join(logsDir, 'error.log'),
            level: 'error',
            maxsize: 10485760, // 10MB
            maxFiles: 5,
            format: logFormat
        })
    ]
});

// Enhanced logging methods with correlation ID support
const originalLog = logger.log.bind(logger);
logger.log = function(level: string, message: string, meta: LogMeta = {}): winston.Logger {
    const correlationId = getCorrelationId();
    if (correlationId && !meta.correlationId) {
        meta.correlationId = correlationId;
    }
    return originalLog(level, message, meta);
};

// Helper methods for structured logging
logger.logRequest = function(req: { method: string; path: string; ip?: string; get: (header: string) => string }, res: { statusCode: number }, duration: number): void {
    const correlationId = getCorrelationId() || generateCorrelationId();
    this.info('HTTP Request', {
        correlationId,
        method: req.method,
        path: req.path,
        statusCode: res.statusCode,
        duration: `${duration}ms`,
        ip: req.ip,
        userAgent: req.get('user-agent')
    } as RequestLogMeta);
};

logger.logError = function(error: Error, context: Record<string, unknown> = {}): void {
    const correlationId = getCorrelationId() || generateCorrelationId();
    this.error('Error occurred', {
        correlationId,
        error: {
            message: error.message,
            stack: error.stack,
            name: error.name,
            code: (error as Error & { code?: string }).code
        },
        ...context
    } as LogMeta);
};

logger.logServiceCall = function(service: string, method: string, duration: number, success = true, error: Error | null = null): void {
    const correlationId = getCorrelationId() || generateCorrelationId();
    const logData: ServiceCallLogMeta = {
        correlationId,
        service,
        method,
        duration: `${duration}ms`,
        success
    };
    
    if (error) {
        logData.error = {
            message: error.message,
            code: (error as Error & { code?: string }).code
        };
    }
    
    if (success) {
        this.debug('Service call completed', logData);
    } else {
        this.warn('Service call failed', logData);
    }
};

// Create stream for HTTP request logging (if needed)
logger.stream = {
    write: (message: string): void => {
        logger.info(message.trim());
    }
};

// Export enhanced logger with correlation ID helpers
export default Object.assign(logger, {
    generateCorrelationId,
    getCorrelationId,
    withCorrelationId,
    correlationIdStorage
});

