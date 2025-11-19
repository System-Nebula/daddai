/**
 * Test HTTP mode for Memory and Chat services
 */
require('dotenv').config();

console.log('=== Testing HTTP Mode ===\n');

// Test that HTTP servers can be imported
async function testHttpServers() {
    let testsPassed = 0;
    let testsFailed = 0;
    
    // Test 1: Check if HTTP mode can be enabled
    console.log('Test 1: HTTP Mode Configuration');
    process.env.USE_MEMORY_SERVER_HTTP = 'true';
    process.env.USE_CHAT_SERVER_HTTP = 'true';
    
    // Clear require cache to reload with new env vars
    delete require.cache[require.resolve('./src/memoryService')];
    delete require.cache[require.resolve('./src/chatService')];
    
    try {
        const MemoryService = require('../src/memoryService');
        const ChatService = require('../src/chatService');
        
        if (MemoryService.useHttp && ChatService.useHttp) {
            console.log('  ✓ HTTP mode enabled for both services');
            testsPassed++;
        } else {
            console.log('  ✗ HTTP mode not enabled');
            testsFailed++;
        }
    } catch (error) {
        console.log(`  ✗ Error: ${error.message}`);
        testsFailed++;
    }
    
    // Test 2: Check HTTP server paths
    console.log('\nTest 2: HTTP Server Script Paths');
    try {
        const MemoryService = require('../src/memoryService');
        const ChatService = require('../src/chatService');
        const path = require('path');
        const fs = require('fs');
        
        const memoryHttpPath = path.join(__dirname, '..', 'src', 'api', 'memory_server_http.py');
        const chatHttpPath = path.join(__dirname, '..', 'src', 'api', 'chat_server_http.py');
        
        if (fs.existsSync(memoryHttpPath) && fs.existsSync(chatHttpPath)) {
            console.log('  ✓ HTTP server scripts exist');
            console.log(`    Memory: ${memoryHttpPath}`);
            console.log(`    Chat: ${chatHttpPath}`);
            testsPassed++;
        } else {
            console.log('  ✗ HTTP server scripts not found');
            testsFailed++;
        }
    } catch (error) {
        console.log(`  ✗ Error: ${error.message}`);
        testsFailed++;
    }
    
    // Test 3: Check HTTP request methods exist
    console.log('\nTest 3: HTTP Request Methods');
    try {
        const MemoryService = require('../src/memoryService');
        const ChatService = require('../src/chatService');
        
        if (typeof MemoryService._sendHttpRequest === 'function' && 
            typeof ChatService._sendHttpRequest === 'function') {
            console.log('  ✓ HTTP request methods exist');
            testsPassed++;
        } else {
            console.log('  ✗ HTTP request methods not found');
            testsFailed++;
        }
    } catch (error) {
        console.log(`  ✗ Error: ${error.message}`);
        testsFailed++;
    }
    
    // Test 4: Check health check methods
    console.log('\nTest 4: Health Check Methods');
    try {
        const MemoryService = require('../src/memoryService');
        const ChatService = require('../src/chatService');
        
        if (typeof MemoryService.checkHttpServer === 'function' && 
            typeof ChatService.checkHttpServer === 'function') {
            console.log('  ✓ Health check methods exist');
            testsPassed++;
        } else {
            console.log('  ✗ Health check methods not found');
            testsFailed++;
        }
    } catch (error) {
        console.log(`  ✗ Error: ${error.message}`);
        testsFailed++;
    }
    
    console.log('\n=== Test Summary ===');
    console.log(`Passed: ${testsPassed}`);
    console.log(`Failed: ${testsFailed}`);
    
    if (testsFailed === 0) {
        console.log('\n✓ All HTTP mode tests passed!');
        console.log('\nTo use HTTP mode, set in .env:');
        console.log('  USE_MEMORY_SERVER_HTTP=true');
        console.log('  USE_CHAT_SERVER_HTTP=true');
        process.exit(0);
    } else {
        console.log('\n✗ Some tests failed');
        process.exit(1);
    }
}

testHttpServers().catch(error => {
    console.error('Test error:', error);
    process.exit(1);
});

