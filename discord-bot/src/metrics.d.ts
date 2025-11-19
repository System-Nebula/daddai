/**
 * Type declarations for metrics.js (CommonJS module)
 */

export interface CacheStats {
    hits: number;
    misses: number;
    total: number;
}

export interface CircuitBreakerStats {
    opens: number;
    closes: number;
    halfOpens: number;
}

export interface LatencyStats {
    p50: number;
    p95: number;
    p99: number;
    mean: number;
    min: number;
    max: number;
    count: number;
}

export interface MetricsJSON {
    requests: Record<string, Record<string, number>>;
    errors: Record<string, Record<string, Record<string, number>>>;
    latencies: Record<string, Record<string, LatencyStats>>;
    cache: {
        hits: number;
        misses: number;
        total: number;
        hitRate: number;
    };
    circuitBreakers: Record<string, CircuitBreakerStats>;
    uptime: number;
}

export class MetricsCollector {
    requestCounts: Map<string, Map<string, number>>;
    errorCounts: Map<string, Map<string, Map<string, number>>>;
    latencies: Map<string, Map<string, number[]>>;
    cacheStats: CacheStats;
    circuitBreakerStats: Map<string, CircuitBreakerStats>;
    startTime: number;

    recordRequest(service: string, method: string, latency: number, success?: boolean, error?: Error | null): void;
    recordCacheHit(): void;
    recordCacheMiss(): void;
    recordCircuitBreakerEvent(service: string, event: string): void;
    getLatencyStats(service: string, method: string): LatencyStats;
    getErrorRate(service: string, method: string): number;
    getPrometheusMetrics(): string;
    getMetricsJSON(): MetricsJSON;
    reset(): void;
}

declare const metricsCollector: MetricsCollector;

// CommonJS export
export = metricsCollector;
export default metricsCollector;
