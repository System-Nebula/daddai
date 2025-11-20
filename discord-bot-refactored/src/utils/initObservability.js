/**
 * Initialize Observability Stack
 * Call this at the start of your application to set up OpenTelemetry
 * 
 * Usage:
 *   require('./src/utils/initObservability').initialize();
 */

const { initializeOpenTelemetry } = require('./observability');
const { startPerformanceMonitoring } = require('./performanceMonitor');
const logger = require('../logger');

/**
 * Initialize all observability features
 */
function initialize() {
    // Initialize OpenTelemetry first
    if (process.env.ENABLE_OPENTELEMETRY !== 'false') {
        try {
            initializeOpenTelemetry();
            logger.info('[Observability] OpenTelemetry initialized successfully');
        } catch (error) {
            logger.error('[Observability] Failed to initialize OpenTelemetry', {
                error: error.message,
                stack: error.stack,
            });
        }
    } else {
        logger.info('[Observability] OpenTelemetry disabled via ENABLE_OPENTELEMETRY=false');
    }

    // Start performance monitoring
    if (process.env.ENABLE_PERFORMANCE_MONITORING !== 'false') {
        const intervalMs = parseInt(process.env.PERFORMANCE_MONITORING_INTERVAL || '10000', 10);
        try {
            startPerformanceMonitoring(intervalMs);
            logger.info('[Observability] Performance monitoring started', { intervalMs });
        } catch (error) {
            logger.error('[Observability] Failed to start performance monitoring', {
                error: error.message,
            });
        }
    }
}

module.exports = {
    initialize,
};

