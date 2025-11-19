/**
 * Prometheus-style metrics collection for the Discord bot.
 * Tracks request counts, latencies, error rates, and other performance metrics.
 */
const logger = require('./logger');

class MetricsCollector {
    constructor() {
        // Request counters: { service: { method: count } }
        this.requestCounts = new Map();
        
        // Error counters: { service: { method: { errorType: count } } }
        this.errorCounts = new Map();
        
        // Latency histograms: { service: { method: [latencies] } }
        this.latencies = new Map();
        
        // Cache statistics
        this.cacheStats = {
            hits: 0,
            misses: 0,
            total: 0
        };
        
        // Circuit breaker statistics
        this.circuitBreakerStats = new Map();
        
        // Start time for uptime calculation
        this.startTime = Date.now();
    }
    
    /**
     * Record a request
     * @param {string} service - Service name (e.g., 'rag', 'chat', 'memory')
     * @param {string} method - Method name (e.g., 'query', 'store')
     * @param {number} latency - Request latency in milliseconds
     * @param {boolean} success - Whether request succeeded
     * @param {Error} error - Error object if failed
     */
    recordRequest(service, method, latency, success = true, error = null) {
        // Initialize service if needed
        if (!this.requestCounts.has(service)) {
            this.requestCounts.set(service, new Map());
            this.errorCounts.set(service, new Map());
            this.latencies.set(service, new Map());
        }
        
        const serviceCounts = this.requestCounts.get(service);
        const serviceErrors = this.errorCounts.get(service);
        const serviceLatencies = this.latencies.get(service);
        
        // Increment request count
        if (!serviceCounts.has(method)) {
            serviceCounts.set(method, 0);
        }
        serviceCounts.set(method, serviceCounts.get(method) + 1);
        
        // Record latency
        if (!serviceLatencies.has(method)) {
            serviceLatencies.set(method, []);
        }
        const methodLatencies = serviceLatencies.get(method);
        methodLatencies.push(latency);
        
        // Keep only last 1000 latencies per method to prevent memory issues
        if (methodLatencies.length > 1000) {
            methodLatencies.shift();
        }
        
        // Record error if failed
        if (!success || error) {
            if (!serviceErrors.has(method)) {
                serviceErrors.set(method, new Map());
            }
            const methodErrors = serviceErrors.get(method);
            const errorType = error?.code || error?.name || error?.message || 'unknown';
            methodErrors.set(errorType, (methodErrors.get(errorType) || 0) + 1);
        }
    }
    
    /**
     * Record cache hit
     */
    recordCacheHit() {
        this.cacheStats.hits++;
        this.cacheStats.total++;
    }
    
    /**
     * Record cache miss
     */
    recordCacheMiss() {
        this.cacheStats.misses++;
        this.cacheStats.total++;
    }
    
    /**
     * Record circuit breaker event
     * @param {string} service - Service name
     * @param {string} event - Event type ('open', 'close', 'half_open')
     */
    recordCircuitBreakerEvent(service, event) {
        if (!this.circuitBreakerStats.has(service)) {
            this.circuitBreakerStats.set(service, {
                opens: 0,
                closes: 0,
                halfOpens: 0
            });
        }
        
        const stats = this.circuitBreakerStats.get(service);
        if (event === 'open') stats.opens++;
        else if (event === 'close') stats.closes++;
        else if (event === 'half_open') stats.halfOpens++;
    }
    
    /**
     * Calculate percentile from sorted array
     * @param {Array<number>} sortedArray - Sorted array of numbers
     * @param {number} percentile - Percentile (0-100)
     * @returns {number} Percentile value
     */
    _calculatePercentile(sortedArray, percentile) {
        if (sortedArray.length === 0) return 0;
        const index = Math.ceil((percentile / 100) * sortedArray.length) - 1;
        return sortedArray[Math.max(0, index)];
    }
    
    /**
     * Get latency statistics for a service method
     * @param {string} service - Service name
     * @param {string} method - Method name
     * @returns {Object} Latency statistics
     */
    getLatencyStats(service, method) {
        const serviceLatencies = this.latencies.get(service);
        if (!serviceLatencies || !serviceLatencies.has(method)) {
            return {
                p50: 0,
                p95: 0,
                p99: 0,
                mean: 0,
                min: 0,
                max: 0,
                count: 0
            };
        }
        
        const latencies = [...serviceLatencies.get(method)].sort((a, b) => a - b);
        const sum = latencies.reduce((a, b) => a + b, 0);
        
        return {
            p50: this._calculatePercentile(latencies, 50),
            p95: this._calculatePercentile(latencies, 95),
            p99: this._calculatePercentile(latencies, 99),
            mean: latencies.length > 0 ? sum / latencies.length : 0,
            min: latencies[0] || 0,
            max: latencies[latencies.length - 1] || 0,
            count: latencies.length
        };
    }
    
    /**
     * Get error rate for a service method
     * @param {string} service - Service name
     * @param {string} method - Method name
     * @returns {number} Error rate (0-1)
     */
    getErrorRate(service, method) {
        const serviceCounts = this.requestCounts.get(service);
        const serviceErrors = this.errorCounts.get(service);
        
        if (!serviceCounts || !serviceCounts.has(method)) {
            return 0;
        }
        
        const totalRequests = serviceCounts.get(method);
        if (totalRequests === 0) return 0;
        
        const methodErrors = serviceErrors?.get(method);
        if (!methodErrors) return 0;
        
        const totalErrors = Array.from(methodErrors.values()).reduce((a, b) => a + b, 0);
        return totalErrors / totalRequests;
    }
    
    /**
     * Get all metrics in Prometheus format
     * @returns {string} Prometheus metrics text format
     */
    getPrometheusMetrics() {
        const lines = [];
        
        // Request counts
        for (const [service, methods] of this.requestCounts.entries()) {
            for (const [method, count] of methods.entries()) {
                lines.push(`discord_bot_requests_total{service="${service}",method="${method}"} ${count}`);
            }
        }
        
        // Error counts
        for (const [service, methods] of this.errorCounts.entries()) {
            for (const [method, errors] of methods.entries()) {
                for (const [errorType, count] of errors.entries()) {
                    lines.push(`discord_bot_errors_total{service="${service}",method="${method}",error_type="${errorType}"} ${count}`);
                }
            }
        }
        
        // Latency metrics
        for (const [service, methods] of this.latencies.entries()) {
            for (const [method] of methods.entries()) {
                const stats = this.getLatencyStats(service, method);
                lines.push(`discord_bot_latency_p50{service="${service}",method="${method}"} ${stats.p50}`);
                lines.push(`discord_bot_latency_p95{service="${service}",method="${method}"} ${stats.p95}`);
                lines.push(`discord_bot_latency_p99{service="${service}",method="${method}"} ${stats.p99}`);
                lines.push(`discord_bot_latency_mean{service="${service}",method="${method}"} ${stats.mean}`);
                lines.push(`discord_bot_latency_min{service="${service}",method="${method}"} ${stats.min}`);
                lines.push(`discord_bot_latency_max{service="${service}",method="${method}"} ${stats.max}`);
            }
        }
        
        // Cache statistics
        lines.push(`discord_bot_cache_hits_total ${this.cacheStats.hits}`);
        lines.push(`discord_bot_cache_misses_total ${this.cacheStats.misses}`);
        if (this.cacheStats.total > 0) {
            const hitRate = this.cacheStats.hits / this.cacheStats.total;
            lines.push(`discord_bot_cache_hit_rate ${hitRate}`);
        }
        
        // Circuit breaker statistics
        for (const [service, stats] of this.circuitBreakerStats.entries()) {
            lines.push(`discord_bot_circuit_breaker_opens_total{service="${service}"} ${stats.opens}`);
            lines.push(`discord_bot_circuit_breaker_closes_total{service="${service}"} ${stats.closes}`);
            lines.push(`discord_bot_circuit_breaker_half_opens_total{service="${service}"} ${stats.halfOpens}`);
        }
        
        // Uptime
        const uptime = (Date.now() - this.startTime) / 1000; // seconds
        lines.push(`discord_bot_uptime_seconds ${uptime}`);
        
        return lines.join('\n') + '\n';
    }
    
    /**
     * Get metrics as JSON object
     * @returns {Object} Metrics object
     */
    getMetricsJSON() {
        const metrics = {
            requests: {},
            errors: {},
            latencies: {},
            cache: {
                hits: this.cacheStats.hits,
                misses: this.cacheStats.misses,
                total: this.cacheStats.total,
                hitRate: this.cacheStats.total > 0 ? this.cacheStats.hits / this.cacheStats.total : 0
            },
            circuitBreakers: {},
            uptime: (Date.now() - this.startTime) / 1000
        };
        
        // Request counts
        for (const [service, methods] of this.requestCounts.entries()) {
            metrics.requests[service] = {};
            for (const [method, count] of methods.entries()) {
                metrics.requests[service][method] = count;
            }
        }
        
        // Error counts
        for (const [service, methods] of this.errorCounts.entries()) {
            metrics.errors[service] = {};
            for (const [method, errors] of methods.entries()) {
                metrics.errors[service][method] = {};
                for (const [errorType, count] of errors.entries()) {
                    metrics.errors[service][method][errorType] = count;
                }
            }
        }
        
        // Latency statistics
        for (const [service, methods] of this.latencies.entries()) {
            metrics.latencies[service] = {};
            for (const [method] of methods.entries()) {
                metrics.latencies[service][method] = this.getLatencyStats(service, method);
            }
        }
        
        // Circuit breaker statistics
        for (const [service, stats] of this.circuitBreakerStats.entries()) {
            metrics.circuitBreakers[service] = { ...stats };
        }
        
        return metrics;
    }
    
    /**
     * Reset all metrics
     */
    reset() {
        this.requestCounts.clear();
        this.errorCounts.clear();
        this.latencies.clear();
        this.cacheStats = { hits: 0, misses: 0, total: 0 };
        this.circuitBreakerStats.clear();
        this.startTime = Date.now();
        logger.info('[Metrics] All metrics reset');
    }
}

// Singleton instance
const metricsCollector = new MetricsCollector();

module.exports = metricsCollector;

