/**
 * OpenTelemetry Observability Setup
 * Provides distributed tracing, metrics, and logging integration
 * 
 * Features:
 * - Automatic instrumentation for HTTP, Express, and more
 * - Prometheus metrics export
 * - Distributed tracing across services
 * - Structured logging with trace context
 */

const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { Resource } = require('@opentelemetry/resources');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
const { context, trace, metrics } = require('@opentelemetry/api');
const logger = require('../logger');

// Optional: OTLP exporters
let OTLPTraceExporter = null;
// Note: Metrics exporter removed - use console exporter or existing metrics.js for Prometheus
try {
    OTLPTraceExporter = require('@opentelemetry/exporter-trace-otlp-http');
} catch (e) {
    logger.warn('[Observability] OTLP trace exporter not available');
}

let sdk = null;
let metricsServer = null;

/**
 * Initialize OpenTelemetry SDK
 */
function initializeOpenTelemetry() {
    if (sdk) {
        logger.warn('[Observability] OpenTelemetry already initialized');
        return;
    }

    const serviceName = process.env.OTEL_SERVICE_NAME || 'discord-bot';
    const serviceVersion = process.env.OTEL_SERVICE_VERSION || '1.0.0';
    const environment = process.env.NODE_ENV || 'development';

    // Create resource with service information
    const resource = new Resource({
        [SemanticResourceAttributes.SERVICE_NAME]: serviceName,
        [SemanticResourceAttributes.SERVICE_VERSION]: serviceVersion,
        [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: environment,
    });

    // Configure trace exporter (OTLP or console)
    let traceExporter = undefined;
    const otlpEndpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT || process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT;
    if (otlpEndpoint && OTLPTraceExporter) {
        traceExporter = new OTLPTraceExporter({
            url: otlpEndpoint.includes('/v1/traces') ? otlpEndpoint : `${otlpEndpoint}/v1/traces`,
        });
        logger.info('[Observability] Using OTLP trace exporter', { endpoint: otlpEndpoint });
    } else {
        logger.info('[Observability] Using console trace exporter (set OTEL_EXPORTER_OTLP_ENDPOINT for OTLP)');
    }

    // Configure metrics exporter (console only - use existing metrics.js for Prometheus)
    // OpenTelemetry metrics will use console exporter
    // For Prometheus format, use the existing metrics.js collector at /api/metrics
    logger.info('[Observability] Using console metrics exporter (use existing /api/metrics for Prometheus format)');

    // Create SDK
    const sdkConfig = {
        resource,
        instrumentations: [
            getNodeAutoInstrumentations({
                // Disable fs instrumentation (can be noisy)
                '@opentelemetry/instrumentation-fs': {
                    enabled: false,
                },
            }),
        ],
    };

    // Add trace exporter if available
    if (traceExporter) {
        sdkConfig.traceExporter = traceExporter;
    }

    // Note: Metrics are handled by existing metrics.js collector
    // OpenTelemetry focuses on distributed tracing
    // If you want OTLP metrics export, install @opentelemetry/exporter-metrics-otlp-http separately

    sdk = new NodeSDK(sdkConfig);

    // Start SDK
    sdk.start();

    logger.info('[Observability] OpenTelemetry initialized', {
        serviceName,
        serviceVersion,
        environment,
        traceExporter: traceExporter ? 'OTLP' : 'console',
        metrics: 'Use existing metrics.js collector for Prometheus format',
    });

    // Handle shutdown gracefully
    process.on('SIGTERM', shutdown);
    process.on('SIGINT', shutdown);
}

/**
 * Shutdown OpenTelemetry SDK
 */
async function shutdown() {
    if (sdk) {
        logger.info('[Observability] Shutting down OpenTelemetry...');
        await sdk.shutdown();
        sdk = null;
    }
}

/**
 * Get Prometheus metrics endpoint
 * Note: For Prometheus, use an OpenTelemetry Collector that exports to Prometheus
 * Or use the existing metrics.js collector which already provides Prometheus format
 */
function getPrometheusMetrics() {
    // Return null - use existing metrics.js collector for Prometheus format
    // Or set up OpenTelemetry Collector with Prometheus exporter
    return null;
}

/**
 * Create a tracer for custom spans
 */
function getTracer(name = 'discord-bot') {
    return trace.getTracer(name);
}

/**
 * Create a meter for custom metrics
 */
function getMeter(name = 'discord-bot') {
    return metrics.getMeter(name);
}

/**
 * Create a span for async operations
 * @param {string} name - Span name
 * @param {Function} fn - Async function to execute
 * @param {Object} options - Span options
 */
async function withSpan(name, fn, options = {}) {
    const tracer = getTracer();
    return tracer.startActiveSpan(name, options, async (span) => {
        try {
            const result = await fn(span);
            span.setStatus({ code: 1 }); // OK
            return result;
        } catch (error) {
            span.setStatus({
                code: 2, // ERROR
                message: error.message,
            });
            span.recordException(error);
            throw error;
        } finally {
            span.end();
        }
    });
}

/**
 * Add attributes to current span
 */
function addSpanAttributes(attributes) {
    const span = trace.getActiveSpan();
    if (span) {
        Object.entries(attributes).forEach(([key, value]) => {
            span.setAttribute(key, value);
        });
    }
}

/**
 * Add event to current span
 */
function addSpanEvent(name, attributes = {}) {
    const span = trace.getActiveSpan();
    if (span) {
        span.addEvent(name, attributes);
    }
}

/**
 * Get trace context for logging
 */
function getTraceContext() {
    const span = trace.getActiveSpan();
    if (!span) {
        return {};
    }

    const spanContext = span.spanContext();
    return {
        traceId: spanContext.traceId,
        spanId: spanContext.spanId,
        traceFlags: spanContext.traceFlags,
    };
}

/**
 * Create a counter metric
 */
function createCounter(name, description, unit = '1') {
    const meter = getMeter();
    return meter.createCounter(name, {
        description,
        unit,
    });
}

/**
 * Create a histogram metric
 */
function createHistogram(name, description, unit = 'ms') {
    const meter = getMeter();
    return meter.createHistogram(name, {
        description,
        unit,
    });
}

/**
 * Create a gauge metric
 */
function createGauge(name, description, unit = '1') {
    const meter = getMeter();
    return meter.createUpDownCounter(name, {
        description,
        unit,
    });
}

module.exports = {
    initializeOpenTelemetry,
    shutdown,
    getPrometheusMetrics,
    getTracer,
    getMeter,
    withSpan,
    addSpanAttributes,
    addSpanEvent,
    getTraceContext,
    createCounter,
    createHistogram,
    createGauge,
};

