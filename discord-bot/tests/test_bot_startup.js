/**
 * Comprehensive bot startup test
 * Tests all services initialize correctly without requiring Discord connection
 */
const path = require('path');
require('dotenv').config();

console.log('=== Discord Bot Startup Test ===\n');

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

console.log('Step 1: Testing service imports...\n');

// Test 1: Import all services
test('Import ConversationManager', () => {
    require('../src/conversationManager');
});

test('Import PersistentRAGService', () => {
    require('../src/ragServicePersistent');
});

test('Import ChatService (singleton)', () => {
    const service = require('../src/chatService');
    if (!service || typeof service.chat !== 'function') {
        throw new Error('ChatService not properly exported');
    }
});

test('Import MemoryService (singleton)', () => {
    const service = require('../src/memoryService');
    if (!service || typeof service.storeMemory !== 'function') {
        throw new Error('MemoryService not properly exported');
    }
});

test('Import DocumentService', () => {
    require('../src/documentService');
});

test('Import ConfigManager', () => {
    require('../src/configManager');
});

test('Import logger', () => {
    const logger = require('../src/logger');
    if (!logger.info || !logger.error) {
        throw new Error('Logger methods not available');
    }
});

test('Import rateLimiter', () => {
    require('../src/rateLimiter');
});

test('Import userContext', () => {
    require('../src/userContext');
});

test('Import gopherAgent', () => {
    require('../src/gopherAgentPersistent');
});

test('Import WebServer', () => {
    const WebServer = require('../src/webServer');
    if (typeof WebServer !== 'function') {
        throw new Error('WebServer not a constructor');
    }
});

console.log('\nStep 2: Testing service initialization...\n');

// Test 2: Initialize services (without Discord client)
test('Initialize ConversationManager', () => {
    const ConversationManager = require('../src/conversationManager');
    const PersistentRAGService = require('../src/ragServicePersistent');
    const ragService = new PersistentRAGService();
    const conversationManager = new ConversationManager(ragService);
    if (!conversationManager) {
        throw new Error('ConversationManager failed to initialize');
    }
});

test('Initialize DocumentService', () => {
    const DocumentService = require('../src/documentService');
    const documentService = new DocumentService();
    if (!documentService) {
        throw new Error('DocumentService failed to initialize');
    }
});

test('Initialize ConfigManager', () => {
    const ConfigManager = require('../src/configManager');
    const configManager = new ConfigManager();
    if (!configManager) {
        throw new Error('ConfigManager failed to initialize');
    }
});

test('Initialize WebServer', () => {
    const WebServer = require('../src/webServer');
    const MemoryService = require('../src/memoryService');
    const DocumentService = require('../src/documentService');
    const webServer = new WebServer(MemoryService, new DocumentService(), 3001); // Use different port for testing
    if (!webServer || !webServer.app) {
        throw new Error('WebServer failed to initialize');
    }
});

console.log('\nStep 3: Testing persistent services...\n');

// Test 3: Verify persistent services are singletons
test('ChatService is singleton', () => {
    const service1 = require('../src/chatService');
    const service2 = require('../src/chatService');
    if (service1 !== service2) {
        throw new Error('ChatService is not a singleton');
    }
});

test('MemoryService is singleton', () => {
    const service1 = require('../src/memoryService');
    const service2 = require('../src/memoryService');
    if (service1 !== service2) {
        throw new Error('MemoryService is not a singleton');
    }
});

// Test 4: Check if servers are starting
testAsync('ChatService server process exists', async () => {
    const chatService = require('../src/chatService');
    // Wait a bit for server to start
    await new Promise(resolve => setTimeout(resolve, 2000));
    if (!chatService.serverProcess) {
        throw new Error('ChatService server process not started');
    }
});

testAsync('MemoryService server process exists', async () => {
    const memoryService = require('../src/memoryService');
    // Wait a bit for server to start
    await new Promise(resolve => setTimeout(resolve, 2000));
    if (!memoryService.serverProcess) {
        throw new Error('MemoryService server process not started');
    }
});

console.log('\nStep 4: Testing metrics and logging...\n');

// Test 5: Test metrics
test('Metrics collector records requests', () => {
    const metricsCollector = require('../src/metrics');
    metricsCollector.recordRequest('test', 'testMethod', 100, true);
    const metrics = metricsCollector.getMetricsJSON();
    if (!metrics.requests.test || metrics.requests.test.testMethod !== 1) {
        throw new Error('Metrics not recorded correctly');
    }
});

test('Metrics Prometheus format', () => {
    const metricsCollector = require('../src/metrics');
    const prometheus = metricsCollector.getPrometheusMetrics();
    if (!prometheus || !prometheus.includes('discord_bot_requests_total')) {
        throw new Error('Prometheus format invalid');
    }
});

// Test 6: Test logger
test('Logger generates correlation IDs', () => {
    const logger = require('../src/logger');
    const id = logger.generateCorrelationId();
    if (!id || typeof id !== 'string') {
        throw new Error('Correlation ID not generated');
    }
});

test('Logger preserves correlation ID in context', () => {
    const logger = require('../src/logger');
    const id = logger.generateCorrelationId();
    logger.withCorrelationId(id, () => {
        const currentId = logger.getCorrelationId();
        if (currentId !== id) {
            throw new Error('Correlation ID not preserved');
        }
    });
});

console.log('\nStep 5: Testing circuit breaker and retry logic...\n');

// Test 7: Circuit breaker
testAsync('Circuit breaker executes successfully', async () => {
    const { CircuitBreaker } = require('../src/circuitBreaker');
    const cb = new CircuitBreaker();
    const result = await cb.execute(async () => 'success');
    if (result !== 'success') {
        throw new Error('Circuit breaker execution failed');
    }
});

// Test 8: Retry logic
testAsync('Retry logic retries on failure', async () => {
    const { retryWithBackoff } = require('../src/retryLogic');
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
        throw new Error(`Retry logic failed (attempts: ${attempts})`);
    }
});

console.log('\nStep 6: Testing request queue...\n');

// Test 9: Request queue
testAsync('Request queue processes requests', async () => {
    const { requestQueue, PRIORITY } = require('../src/requestQueue');
    const result = await requestQueue.enqueue(
        async () => 'queued',
        {
            priority: PRIORITY.NORMAL,
            service: 'test',
            method: 'test'
        }
    );
    if (result !== 'queued') {
        throw new Error('Request queue failed');
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
    process.exit(1);
} else {
    console.log('\n✓ All startup tests passed!');
    console.log('\nNote: Persistent servers are running. They will be cleaned up when the process exits.');
    
    // Cleanup
    setTimeout(() => {
        const chatService = require('../src/chatService');
        const memoryService = require('../src/memoryService');
        const { requestQueue } = require('../src/requestQueue');
        
        console.log('\nCleaning up...');
        chatService.shutdown();
        memoryService.shutdown();
        requestQueue.shutdown().then(() => {
            console.log('Cleanup complete.');
            process.exit(0);
        });
    }, 3000);
}

