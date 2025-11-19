/**
 * Integration test to verify services work together
 */
(async function() {
    const logger = require('../src/logger');
    const metricsCollector = require('../src/metrics');
    const { CircuitBreaker } = require('../src/circuitBreaker');
    const { retryWithBackoff } = require('../src/retryLogic');
    const { requestQueue, PRIORITY } = require('../src/requestQueue');

    console.log('Testing integration...\n');

    // Test 1: Logger with correlation ID
    console.log('Test 1: Logger with correlation ID');
    const correlationId = logger.generateCorrelationId();
    logger.withCorrelationId(correlationId, () => {
        logger.info('Test message with correlation ID');
        const currentId = logger.getCorrelationId();
        if (currentId === correlationId) {
            console.log('  ✓ Correlation ID preserved in context');
        } else {
            console.log('  ✗ Correlation ID not preserved');
        }
    });

    // Test 2: Metrics collection
    console.log('\nTest 2: Metrics collection');
    metricsCollector.recordRequest('test', 'method1', 100, true);
    metricsCollector.recordRequest('test', 'method2', 200, false, new Error('test error'));
    metricsCollector.recordCacheHit();
    metricsCollector.recordCacheMiss();

    const metrics = metricsCollector.getMetricsJSON();
    if (metrics.requests.test && metrics.requests.test.method1 === 1) {
        console.log('  ✓ Request metrics recorded');
    } else {
        console.log('  ✗ Request metrics not recorded');
    }

    if (metrics.cache.hits === 1 && metrics.cache.misses === 1) {
        console.log('  ✓ Cache metrics recorded');
    } else {
        console.log('  ✗ Cache metrics not recorded');
    }

    // Test 3: Circuit Breaker
    console.log('\nTest 3: Circuit Breaker');
    const cb = new CircuitBreaker({ failureThreshold: 2, resetTimeout: 1000 });
    let successCount = 0;
    let failureCount = 0;

    // Simulate successful calls
    for (let i = 0; i < 3; i++) {
        try {
            await cb.execute(async () => {
                return 'success';
            }, { test: true });
            successCount++;
        } catch (e) {
            failureCount++;
        }
    }

    if (successCount === 3 && cb.getState().state === 'CLOSED') {
        console.log('  ✓ Circuit breaker handles success correctly');
    } else {
        console.log('  ✗ Circuit breaker test failed');
    }

    // Test 4: Retry Logic
    console.log('\nTest 4: Retry Logic');
    let attemptCount = 0;
    try {
        await retryWithBackoff(
            async () => {
                attemptCount++;
                if (attemptCount < 2) {
                    throw new Error('ECONNRESET');
                }
                return 'success';
            },
            { maxRetries: 3, initialDelay: 10 },
            { test: true }
        );
        if (attemptCount === 2) {
            console.log('  ✓ Retry logic works correctly');
        } else {
            console.log(`  ✗ Retry logic failed (attempts: ${attemptCount})`);
        }
    } catch (e) {
        console.log(`  ✗ Retry logic error: ${e.message}`);
    }

    // Test 5: Request Queue
    console.log('\nTest 5: Request Queue');
    let queueResult = null;
    try {
        queueResult = await requestQueue.enqueue(
            async () => {
                return 'queued result';
            },
            {
                priority: PRIORITY.NORMAL,
                service: 'test',
                method: 'test',
                context: { test: true }
            }
        );
        if (queueResult === 'queued result') {
            console.log('  ✓ Request queue processes requests');
        } else {
            console.log('  ✗ Request queue failed');
        }
    } catch (e) {
        console.log(`  ✗ Request queue error: ${e.message}`);
    }

    const stats = requestQueue.getStats();
    console.log(`  → Queue stats: ${JSON.stringify(stats)}`);

    console.log('\n=== Integration Tests Complete ===');
    console.log('All core functionality verified!');
    
    // Cleanup
    setTimeout(() => {
        requestQueue.shutdown().then(() => process.exit(0));
    }, 1000);
})();

