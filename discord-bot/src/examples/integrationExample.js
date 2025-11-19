/**
 * EXAMPLE: How to integrate OpenTelemetry and observability features
 * 
 * This file shows how to integrate the new observability features into your application.
 * Copy these patterns into your main index.js file.
 */

// 1. Initialize observability FIRST (before any other imports that might make HTTP requests)
require('./utils/initObservability').initialize();

// 2. Import other modules
const express = require('express');
const { observabilityMiddleware } = require('./middleware/observabilityMiddleware');
const { getPrometheusMetrics } = require('./utils/observability');
const { getHealthCheckData } = require('./utils/performanceMonitor');
const enhancedLogger = require('./utils/enhancedLogger');

// 3. Create Express app
const app = express();

// 4. Add observability middleware (before other middleware)
app.use(observabilityMiddleware);

// 5. Add routes
app.get('/health', async (req, res) => {
    const healthData = await getHealthCheckData();
    res.json(healthData);
});

// 6. Add Prometheus metrics endpoint
app.get('/metrics', async (req, res) => {
    const metricsHandler = getPrometheusMetrics();
    if (metricsHandler) {
        return metricsHandler(req, res);
    }
    res.status(503).json({ error: 'Metrics not available' });
});

// 7. Example: Use enhanced logger with trace context
app.get('/api/data', async (req, res) => {
    enhancedLogger.info('Fetching data', { userId: req.user?.id });
    
    try {
        const data = await fetchData();
        enhancedLogger.info('Data fetched successfully', { dataSize: data.length });
        res.json(data);
    } catch (error) {
        enhancedLogger.error('Failed to fetch data', { error: error.message });
        res.status(500).json({ error: 'Internal server error' });
    }
});

// 8. Example: Use withSpan for custom tracing
const { withSpan } = require('./utils/observability');

app.post('/api/process', async (req, res) => {
    await withSpan('process_data', async (span) => {
        span.setAttribute('input.size', req.body.data?.length || 0);
        
        const result = await processData(req.body.data);
        
        span.setAttribute('output.size', result.length);
        span.addEvent('processing_complete');
        
        res.json(result);
    });
});

function fetchData() {
    return Promise.resolve([1, 2, 3]);
}

function processData(data) {
    return Promise.resolve(data.map(x => x * 2));
}

module.exports = app;

