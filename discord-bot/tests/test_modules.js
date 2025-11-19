/**
 * Test script to verify all new modules load correctly
 */
const path = require('path');

const modules = [
    'src/memoryService',
    'src/chatService',
    'src/circuitBreaker',
    'src/retryLogic',
    'src/metrics',
    'src/logger',
    'src/requestQueue',
    'src/streamingResponse',
    'src/webServer'
];

let passed = 0;
let failed = 0;
const errors = [];

console.log('Testing module imports...\n');

for (const modulePath of modules) {
    try {
        const module = require(`../${modulePath}`);
        console.log(`✓ ${modulePath} loads correctly`);
        passed++;
        
        // Test basic functionality for key modules
        if (modulePath === 'src/circuitBreaker') {
            const { CircuitBreaker } = module;
            const cb = new CircuitBreaker();
            if (cb.getState().state === 'CLOSED') {
                console.log(`  → CircuitBreaker state: ${cb.getState().state}`);
            }
        }
        
        if (modulePath === 'src/retryLogic') {
            const { retryWithBackoff, isRetryableError } = module;
            if (typeof retryWithBackoff === 'function' && typeof isRetryableError === 'function') {
                console.log(`  → retryWithBackoff and isRetryableError functions available`);
            }
        }
        
        if (modulePath === 'src/metrics') {
            const metrics = module.getMetricsJSON();
            if (metrics && typeof metrics === 'object') {
                console.log(`  → Metrics collector working (uptime: ${metrics.uptime}s)`);
            }
        }
        
        if (modulePath === 'src/logger') {
            const logger = module;
            if (logger.info && logger.error && logger.warn) {
                console.log(`  → Logger methods available`);
            }
        }
        
        if (modulePath === 'src/requestQueue') {
            const { requestQueue, PRIORITY } = module;
            if (requestQueue && PRIORITY) {
                const stats = requestQueue.getStats();
                console.log(`  → RequestQueue working (queueSize: ${stats.queueSize})`);
            }
        }
        
    } catch (error) {
        console.error(`✗ ${modulePath} failed to load: ${error.message}`);
        console.error(`  Stack: ${error.stack.split('\n')[1]}`);
        failed++;
        errors.push({ module: modulePath, error: error.message });
    }
}

console.log(`\n=== Test Results ===`);
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);

if (failed > 0) {
    console.log(`\nErrors:`);
    errors.forEach(({ module, error }) => {
        console.log(`  - ${module}: ${error}`);
    });
    process.exit(1);
} else {
    console.log(`\n✓ All modules loaded successfully!`);
    process.exit(0);
}

