/**
 * Test service communication with persistent servers
 */
require('dotenv').config();

const ChatService = require('../src/chatService');
const MemoryService = require('../src/memoryService');

console.log('=== Service Communication Test ===\n');

let testsPassed = 0;
let testsFailed = 0;

async function waitForServer(service, serviceName, timeout = 30000) {
    const startTime = Date.now();
    while (!service.isReady && (Date.now() - startTime) < timeout) {
        await new Promise(resolve => setTimeout(resolve, 500));
    }
    if (!service.isReady) {
        throw new Error(`${serviceName} server did not become ready within ${timeout}ms`);
    }
}

async function testService(name, testFn) {
    try {
        await testFn();
        console.log(`✓ ${name}`);
        testsPassed++;
    } catch (error) {
        console.error(`✗ ${name}: ${error.message}`);
        testsFailed++;
    }
}

async function runTests() {
    console.log('Waiting for servers to be ready...\n');
    
    // Wait for servers to be ready
    await testService('ChatService server ready', async () => {
        await waitForServer(ChatService, 'ChatService', 30000);
    });
    
    await testService('MemoryService server ready', async () => {
        await waitForServer(MemoryService, 'MemoryService', 30000);
    });
    
    console.log('\nTesting service communication...\n');
    
    // Test ChatService ping
    await testService('ChatService ping', async () => {
        // ChatService doesn't have a ping method, but we can test by checking if server is ready
        if (!ChatService.isReady) {
            throw new Error('ChatService not ready');
        }
    });
    
    // Test MemoryService ping (via sendRequest)
    await testService('MemoryService ping', async () => {
        const result = await MemoryService.sendRequest({
            method: 'ping',
            params: {}
        });
        if (!result || result.status !== 'ok') {
            throw new Error('MemoryService ping failed');
        }
    });
    
    // Test MemoryService storeMemory
    await testService('MemoryService storeMemory', async () => {
        const testChannelId = 'test_channel_' + Date.now();
        const result = await MemoryService.storeMemory(
            testChannelId,
            'Test memory content',
            'conversation',
            {},
            'Test Channel',
            'test_user',
            'TestUser'
        );
        if (!result || !result.success) {
            throw new Error('MemoryService storeMemory failed');
        }
    });
    
    // Test MemoryService getAllChannels
    await testService('MemoryService getAllChannels', async () => {
        const result = await MemoryService.getAllChannels();
        if (!result || !result.channels) {
            throw new Error('MemoryService getAllChannels failed');
        }
    });
    
    // Test ChatService chat (simple message)
    await testService('ChatService chat', async () => {
        const result = await ChatService.chat('Hello, this is a test message.');
        if (!result || typeof result !== 'string' || result.length === 0) {
            throw new Error('ChatService chat failed or returned empty result');
        }
    });
    
    console.log('\n=== Service Communication Test Summary ===');
    console.log(`Passed: ${testsPassed}`);
    console.log(`Failed: ${testsFailed}`);
    
    if (testsFailed > 0) {
        process.exit(1);
    } else {
        console.log('\n✓ All service communication tests passed!');
        console.log('\nCleaning up...');
        ChatService.shutdown();
        MemoryService.shutdown();
        setTimeout(() => {
            process.exit(0);
        }, 2000);
    }
}

runTests().catch(error => {
    console.error('Test error:', error);
    process.exit(1);
});

