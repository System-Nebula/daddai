/**
 * Performance Monitoring Utilities
 * Tracks memory usage, CPU, and performance metrics
 */

const { createGauge, createHistogram, addSpanAttributes } = require('./observability');
// Use regular logger - enhancedLogger requires observability to be initialized first
const logger = require('../logger');

// Create metrics
const memoryUsageGauge = createGauge('discord_bot_memory_usage_bytes', 'Memory usage in bytes');
const cpuUsageGauge = createGauge('discord_bot_cpu_usage_percent', 'CPU usage percentage');
const eventLoopLagHistogram = createHistogram('discord_bot_event_loop_lag_ms', 'Event loop lag in milliseconds');
const activeHandlesGauge = createGauge('discord_bot_active_handles', 'Number of active handles');
const activeRequestsGauge = createGauge('discord_bot_active_requests', 'Number of active requests');

let monitoringInterval = null;

/**
 * Get current memory usage
 */
function getMemoryUsage() {
    const usage = process.memoryUsage();
    return {
        rss: usage.rss, // Resident Set Size
        heapTotal: usage.heapTotal,
        heapUsed: usage.heapUsed,
        external: usage.external,
        arrayBuffers: usage.arrayBuffers,
    };
}

/**
 * Get current CPU usage (simplified - Node.js doesn't provide direct CPU usage)
 */
function getCPUUsage() {
    const cpuUsage = process.cpuUsage();
    return {
        user: cpuUsage.user,
        system: cpuUsage.system,
    };
}

/**
 * Measure event loop lag
 */
function measureEventLoopLag() {
    return new Promise((resolve) => {
        const start = process.hrtime.bigint();
        setImmediate(() => {
            const delta = process.hrtime.bigint() - start;
            const lagMs = Number(delta) / 1_000_000; // Convert to milliseconds
            resolve(lagMs);
        });
    });
}

/**
 * Get process resource usage
 */
function getResourceUsage() {
    const memory = getMemoryUsage();
    const cpu = getCPUUsage();
    const lag = measureEventLoopLag();

    return {
        memory,
        cpu,
        lag,
        uptime: process.uptime(),
        pid: process.pid,
        activeHandles: process._getActiveHandles?.()?.length || 0,
        activeRequests: process._getActiveRequests?.()?.length || 0,
    };
}

/**
 * Record performance metrics
 */
async function recordPerformanceMetrics() {
    try {
        const memory = getMemoryUsage();
        const lag = await measureEventLoopLag();
        const activeHandles = process._getActiveHandles?.()?.length || 0;
        const activeRequests = process._getActiveRequests?.()?.length || 0;

        // Record metrics
        memoryUsageGauge.add(memory.heapUsed, {
            type: 'heap',
        });
        memoryUsageGauge.add(memory.rss, {
            type: 'rss',
        });
        eventLoopLagHistogram.record(lag);
        activeHandlesGauge.add(activeHandles);
        activeRequestsGauge.add(activeRequests);

        // Add to current span if available
        addSpanAttributes({
            'process.memory.heap_used': memory.heapUsed,
            'process.memory.rss': memory.rss,
            'process.event_loop_lag': lag,
        });

        return {
            memory,
            lag,
            activeHandles,
            activeRequests,
        };
    } catch (error) {
        logger.error('Failed to record performance metrics', { error: error.message });
        return null;
    }
}

/**
 * Start performance monitoring
 * @param {number} intervalMs - Monitoring interval in milliseconds (default: 10000)
 */
function startPerformanceMonitoring(intervalMs = 10000) {
    if (monitoringInterval) {
        logger.warn('Performance monitoring already started');
        return;
    }

    logger.info('Starting performance monitoring', { intervalMs });

    monitoringInterval = setInterval(async () => {
        const metrics = await recordPerformanceMetrics();
        if (metrics) {
            logger.debug('Performance metrics recorded', metrics);
        }
    }, intervalMs);

    // Record initial metrics
    recordPerformanceMetrics();
}

/**
 * Stop performance monitoring
 */
function stopPerformanceMonitoring() {
    if (monitoringInterval) {
        clearInterval(monitoringInterval);
        monitoringInterval = null;
        logger.info('Performance monitoring stopped');
    }
}

/**
 * Get health check data with performance metrics
 */
async function getHealthCheckData() {
    const resourceUsage = getResourceUsage();
    const memory = resourceUsage.memory;

    // Calculate memory usage percentage (rough estimate)
    const memoryUsagePercent = (memory.heapUsed / memory.heapTotal) * 100;

    return {
        status: 'healthy',
        timestamp: new Date().toISOString(),
        uptime: resourceUsage.uptime,
        memory: {
            ...memory,
            usagePercent: memoryUsagePercent,
        },
        eventLoopLag: resourceUsage.lag,
        activeHandles: resourceUsage.activeHandles,
        activeRequests: resourceUsage.activeRequests,
    };
}

module.exports = {
    getMemoryUsage,
    getCPUUsage,
    getResourceUsage,
    measureEventLoopLag,
    recordPerformanceMetrics,
    startPerformanceMonitoring,
    stopPerformanceMonitoring,
    getHealthCheckData,
};

