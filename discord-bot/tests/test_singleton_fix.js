/**
 * Test that services are singleton instances
 */
const ChatService = require('../src/chatService');
const MemoryService = require('../src/memoryService');

console.log('Testing singleton services...\n');

// Check types
console.log('ChatService type:', typeof ChatService);
console.log('MemoryService type:', typeof MemoryService);

// Check if they have the expected methods
console.log('\nChatService methods:');
console.log('  - chat:', typeof ChatService.chat === 'function' ? '✓' : '✗');
console.log('  - sendRequest:', typeof ChatService.sendRequest === 'function' ? '✓' : '✗');
console.log('  - isReady:', typeof ChatService.isReady !== 'undefined' ? '✓' : '✗');

console.log('\nMemoryService methods:');
console.log('  - storeMemory:', typeof MemoryService.storeMemory === 'function' ? '✓' : '✗');
console.log('  - sendRequest:', typeof MemoryService.sendRequest === 'function' ? '✓' : '✗');
console.log('  - isReady:', typeof MemoryService.isReady !== 'undefined' ? '✓' : '✗');

// Verify they're instances, not constructors
if (typeof ChatService === 'object' && ChatService.chat) {
    console.log('\n✓ ChatService is a singleton instance (not a constructor)');
} else {
    console.log('\n✗ ChatService is not a singleton instance');
    process.exit(1);
}

if (typeof MemoryService === 'object' && MemoryService.storeMemory) {
    console.log('✓ MemoryService is a singleton instance (not a constructor)');
} else {
    console.log('✗ MemoryService is not a singleton instance');
    process.exit(1);
}

console.log('\n✓ All tests passed! Services are correctly exported as singletons.');

