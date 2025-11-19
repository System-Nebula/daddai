/**
 * Complete end-to-end test of the Discord bot
 * Tests all services, integrations, and features together
 */
require('dotenv').config();

console.log('=== Complete Bot Test ===\n');
console.log('This test verifies all bot components work together:\n');

const logger = require('../src/logger');
const metricsCollector = require('../src/metrics');
const { CircuitBreaker } = require('../src/circuitBreaker');
const { retryWithBackoff } = require('../src/retryLogic');
const { requestQueue, PRIORITY } = require('../src/requestQueue');
const ChatService = require('../src/chatService');
const MemoryService = require('../src/memoryService');
const { createCircuitBreaker } = require('../src/circuitBreaker');

let testsPassed = 0;
let testsFailed = 0;
const errors = [];

function test(name, fn) {
    try {
        fn();
        console.log(`✓ ${name}`);
        testsPassed++;
    } catch (error) {
        console.error(`✗ ${name}: ${error.message}`);
        errors.push({ name, error: error.message });
        testsFailed++;
    }
}

async function testAsync(name, fn) {
    try {
        await fn();
        console.log(`✓ ${name}`);
        testsPassed++;
    } catch (error) {
        console.error(`✗ ${name}: ${error.message}`);
        errors.push({ name, error: error.message });
        testsFailed++;
    }
}

async function waitForServer(service, serviceName, timeout = 30000) {
    const startTime = Date.now();
    while (!service.isReady && (Date.now() - startTime) < timeout) {
        await new Promise(resolve => setTimeout(resolve, 500));
    }
    if (!service.isReady) {
        throw new Error(`${serviceName} server did not become ready within ${timeout}ms`);
    }
}

async function runTests() {
    console.log('Phase 1: Service Initialization\n');
    
    // Wait for persistent servers
    await testAsync('Wait for ChatService server', async () => {
        await waitForServer(ChatService, 'ChatService', 30000);
    });
    
    await testAsync('Wait for MemoryService server', async () => {
        await waitForServer(MemoryService, 'MemoryService', 30000);
    });
    
    console.log('\nPhase 2: Core Features\n');
    
    // Test logging with correlation ID
    await testAsync('Logger with correlation ID', async () => {
        const id = logger.generateCorrelationId();
        logger.withCorrelationId(id, () => {
            logger.info('Test message');
            if (logger.getCorrelationId() !== id) {
                throw new Error('Correlation ID not preserved');
            }
        });
    });
    
    // Test metrics
    await testAsync('Metrics collection', async () => {
        metricsCollector.recordRequest('test', 'test', 100, true);
        const metrics = metricsCollector.getMetricsJSON();
        if (!metrics.requests.test) {
            throw new Error('Metrics not recorded');
        }
    });
    
    // Test circuit breaker
    await testAsync('Circuit breaker with service call', async () => {
        const cb = createCircuitBreaker({ failureThreshold: 3 });
        const result = await cb.execute(async () => {
            // Simulate a service call
            return 'success';
        }, { service: 'test' });
        if (result !== 'success') {
            throw new Error('Circuit breaker failed');
        }
    });
    
    // Test retry logic
    await testAsync('Retry logic with service call', async () => {
        let attempts = 0;
        const result = await retryWithBackoff(
            async () => {
                attempts++;
                if (attempts < 2) {
                    throw new Error('ECONNRESET');
                }
                return 'success';
            },
            { maxRetries: 3, initialDelay: 10 }
        );
        if (result !== 'success' || attempts !== 2) {
            throw new Error(`Retry failed (attempts: ${attempts})`);
        }
    });
    
    // Test request queue
    await testAsync('Request queue with priority', async () => {
        const result = await requestQueue.enqueue(
            async () => 'queued',
            {
                priority: PRIORITY.HIGH,
                service: 'test',
                method: 'test'
            }
        );
        if (result !== 'queued') {
            throw new Error('Request queue failed');
        }
    });
    
    console.log('\nPhase 3: Service Communication\n');
    
    // Test MemoryService operations
    await testAsync('MemoryService - store and retrieve', async () => {
        const testChannelId = 'test_' + Date.now();
        await MemoryService.storeMemory(testChannelId, 'Test memory', 'conversation');
        const channels = await MemoryService.getAllChannels();
        if (!channels || !channels.channels) {
            throw new Error('Failed to retrieve channels');
        }
    });
    
    // Test ChatService
    await testAsync('ChatService - simple chat', async () => {
        const response = await ChatService.chat('Say hello!');
        if (!response || typeof response !== 'string' || response.length === 0) {
            throw new Error('ChatService returned invalid response');
        }
    });
    
    console.log('\nPhase 4: Integration Tests\n');
    
    // Test circuit breaker + retry + metrics together
    await testAsync('Circuit breaker + Retry + Metrics integration', async () => {
        const cb = createCircuitBreaker();
        let attempts = 0;
        
        const result = await retryWithBackoff(
            async () => {
                const startTime = Date.now();
                const result = await cb.execute(async () => {
                    attempts++;
                    if (attempts < 2) {
                        throw new Error('ECONNRESET');
                    }
                    return 'success';
                }, { service: 'integration_test' });
                const duration = Date.now() - startTime;
                metricsCollector.recordRequest('integration_test', 'test', duration, true);
                return result;
            },
            { maxRetries: 3, initialDelay: 10 }
        );
        
        if (result !== 'success') {
            throw new Error('Integration test failed');
        }
    });
    
    // Test request queue + circuit breaker
    await testAsync('Request queue + Circuit breaker integration', async () => {
        const cb = createCircuitBreaker();
        const result = await requestQueue.enqueue(
            async () => {
                return await cb.execute(async () => 'success', { service: 'queue_test' });
            },
            {
                priority: PRIORITY.NORMAL,
                service: 'queue_test',
                method: 'test'
            }
        );
        if (result !== 'success') {
            throw new Error('Queue + Circuit breaker integration failed');
        }
    });
    
    console.log('\nPhase 5: Error Handling\n');
    
    // Test circuit breaker opens on failures
    await testAsync('Circuit breaker opens on consecutive failures', async () => {
        const cb = createCircuitBreaker({ failureThreshold: 2, resetTimeout: 1000 });
        
        // Cause failures
        try {
            await cb.execute(async () => { throw new Error('test error'); }, {});
        } catch (e) {}
        
        try {
            await cb.execute(async () => { throw new Error('test error'); }, {});
        } catch (e) {}
        
        // Circuit should be open now
        const state = cb.getState();
        if (state.state !== 'OPEN') {
            throw new Error(`Circuit breaker should be OPEN but is ${state.state}`);
        }
    });
    
    // Test retry gives up after max retries
    await testAsync('Retry logic gives up after max retries', async () => {
        let attempts = 0;
        try {
            await retryWithBackoff(
                async () => {
                    attempts++;
                    throw new Error('ECONNRESET');
                },
                { maxRetries: 2, initialDelay: 10 }
            );
            throw new Error('Should have thrown error');
        } catch (e) {
            if (attempts !== 3) { // Initial + 2 retries
                throw new Error(`Expected 3 attempts but got ${attempts}`);
            }
        }
    });
    
    console.log('\n=== Test Summary ===\n');
    console.log(`Passed: ${testsPassed}`);
    console.log(`Failed: ${testsFailed}`);
    
    if (testsFailed > 0) {
        console.log('\nErrors:');
        errors.forEach(({ name, error }) => {
            console.log(`  - ${name}: ${error}`);
        });
    } else {
        console.log('\n✓ All tests passed!');
        
        // Print final metrics
        const metrics = metricsCollector.getMetricsJSON();
        console.log('\nFinal Metrics:');
        console.log(`  - Total requests: ${metrics.requests.integration_test?.test || 0}`);
        console.log(`  - Cache hit rate: ${(metrics.cache.hitRate * 100).toFixed(2)}%`);
        console.log(`  - Uptime: ${metrics.uptime.toFixed(2)}s`);
    }
    
    // Cleanup
    console.log('\nCleaning up...');
    ChatService.shutdown();
    MemoryService.shutdown();
    requestQueue.shutdown().then(() => {
        setTimeout(() => {
            process.exit(testsFailed > 0 ? 1 : 0);
        }, 2000);
    });
}

runTests().catch(error => {
    console.error('Test error:', error);
    process.exit(1);
});

