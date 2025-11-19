/**
 * Performance comparison: HTTP vs stdin/stdout
 */
require('dotenv').config();
const http = require('http');

console.log('=== HTTP vs stdin/stdout Comparison ===\n');

// Test stdin/stdout mode (default)
async function testStdinStdout() {
    console.log('Testing stdin/stdout mode...');
    const startTime = Date.now();
    
    // Clear cache and reload with stdin/stdout mode
    delete process.env.USE_MEMORY_SERVER_HTTP;
    delete process.env.USE_CHAT_SERVER_HTTP;
    delete require.cache[require.resolve('./src/memoryService')];
    delete require.cache[require.resolve('./src/chatService')];
    
    const MemoryService = require('../src/memoryService');
    const ChatService = require('../src/chatService');
    
    // Wait for servers to be ready
    const maxWait = 30000;
    const startWait = Date.now();
    while ((!MemoryService.isReady || !ChatService.isReady) && (Date.now() - startWait) < maxWait) {
        await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    if (!MemoryService.isReady || !ChatService.isReady) {
        console.log('  ⚠ Servers not ready within timeout');
        return null;
    }
    
    // Test ping operations
    const pingStart = Date.now();
    try {
        await MemoryService.sendRequest({ method: 'ping', params: {} });
        await ChatService.sendRequest({ method: 'ping', params: {} });
        const pingTime = Date.now() - pingStart;
        
        const totalTime = Date.now() - startTime;
        return {
            mode: 'stdin/stdout',
            startupTime: totalTime,
            pingTime: pingTime,
            ready: true
        };
    } catch (error) {
        console.log(`  ✗ Error: ${error.message}`);
        return null;
    }
}

// Test HTTP mode
async function testHttp() {
    console.log('\nTesting HTTP mode...');
    const startTime = Date.now();
    
    // Set HTTP mode
    process.env.USE_MEMORY_SERVER_HTTP = 'true';
    process.env.USE_CHAT_SERVER_HTTP = 'true';
    delete require.cache[require.resolve('./src/memoryService')];
    delete require.cache[require.resolve('./src/chatService')];
    
    const MemoryService = require('../src/memoryService');
    const ChatService = require('../src/chatService');
    
    // Wait for servers to be ready
    const maxWait = 30000;
    const startWait = Date.now();
    while ((!MemoryService.isReady || !ChatService.isReady) && (Date.now() - startWait) < maxWait) {
        await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    if (!MemoryService.isReady || !ChatService.isReady) {
        console.log('  ⚠ HTTP servers not ready within timeout');
        console.log('  Note: HTTP servers need to be started separately');
        return null;
    }
    
    // Test ping operations
    const pingStart = Date.now();
    try {
        await MemoryService.sendRequest({ method: 'ping', params: {} });
        await ChatService.sendRequest({ method: 'ping', params: {} });
        const pingTime = Date.now() - pingStart;
        
        const totalTime = Date.now() - startTime;
        return {
            mode: 'HTTP',
            startupTime: totalTime,
            pingTime: pingTime,
            ready: true
        };
    } catch (error) {
        console.log(`  ✗ Error: ${error.message}`);
        return null;
    }
}

async function runComparison() {
    console.log('This test compares stdin/stdout vs HTTP modes.\n');
    console.log('Note: HTTP servers need to be started separately for full testing.\n');
    
    const stdinResult = await testStdinStdout();
    const httpResult = await testHttp();
    
    console.log('\n=== Comparison Results ===\n');
    
    if (stdinResult) {
        console.log('stdin/stdout Mode:');
        console.log(`  Startup time: ${stdinResult.startupTime}ms`);
        console.log(`  Ping time: ${stdinResult.pingTime}ms`);
        console.log(`  Status: ✓ Ready`);
    } else {
        console.log('stdin/stdout Mode: Not tested (servers not ready)');
    }
    
    if (httpResult) {
        console.log('\nHTTP Mode:');
        console.log(`  Startup time: ${httpResult.startupTime}ms`);
        console.log(`  Ping time: ${httpResult.pingTime}ms`);
        console.log(`  Status: ✓ Ready`);
    } else {
        console.log('\nHTTP Mode: Not tested (servers need to be started separately)');
    }
    
    console.log('\n=== Recommendation ===\n');
    console.log('stdin/stdout Mode (Default):');
    console.log('  ✓ Faster (no HTTP overhead)');
    console.log('  ✓ Simpler (no port management)');
    console.log('  ✓ Lower latency');
    console.log('  ✗ Harder to debug');
    console.log('  ✗ No external access');
    console.log('\nHTTP Mode (Optional):');
    console.log('  ✓ Easier debugging (curl, Postman)');
    console.log('  ✓ External access');
    console.log('  ✓ Standard monitoring tools');
    console.log('  ✗ Slightly slower (HTTP overhead)');
    console.log('  ✗ Requires port management');
    console.log('\nRecommendation:');
    console.log('  - Use stdin/stdout for production (default)');
    console.log('  - Use HTTP for development/debugging');
    console.log('  - Use HTTP if you need external access');
    
    // Cleanup
    if (stdinResult) {
        const MemoryService = require('../src/memoryService');
        const ChatService = require('../src/chatService');
        MemoryService.shutdown();
        ChatService.shutdown();
    }
    
    setTimeout(() => process.exit(0), 2000);
}

runComparison().catch(error => {
    console.error('Comparison error:', error);
    process.exit(1);
});

