/**
 * Test bot syntax and imports without starting Discord connection
 */
require('dotenv').config();

console.log('=== Bot Syntax and Import Test ===\n');

let errors = [];

try {
    // Test that all required modules can be imported
    console.log('Testing imports...');
    
    const { Client, GatewayIntentBits } = require('discord.js');
    console.log('✓ discord.js');
    
    const ConversationManager = require('../src/conversationManager');
    console.log('✓ ConversationManager');
    
    const PersistentRAGService = require('../src/ragServicePersistent');
    console.log('✓ PersistentRAGService');
    
    const ChatService = require('../src/chatService');
    console.log('✓ ChatService');
    
    const MemoryService = require('../src/memoryService');
    console.log('✓ MemoryService');
    
    const DocumentService = require('../src/documentService');
    console.log('✓ DocumentService');
    
    const ConfigManager = require('../src/configManager');
    console.log('✓ ConfigManager');
    
    const logger = require('../src/logger');
    console.log('✓ logger');
    
    const rateLimiter = require('../src/rateLimiter');
    console.log('✓ rateLimiter');
    
    const userContext = require('../src/userContext');
    console.log('✓ userContext');
    
    const gopherAgent = require('../src/gopherAgentPersistent');
    console.log('✓ gopherAgent');
    
    const WebServer = require('../src/webServer');
    console.log('✓ WebServer');
    
    // Test that services can be instantiated
    console.log('\nTesting service instantiation...');
    
    const ragService = new PersistentRAGService();
    console.log('✓ PersistentRAGService instance');
    
    const conversationManager = new ConversationManager(ragService);
    console.log('✓ ConversationManager instance');
    
    const documentService = new DocumentService();
    console.log('✓ DocumentService instance');
    
    const configManager = new ConfigManager();
    console.log('✓ ConfigManager instance');
    
    const webServer = new WebServer(MemoryService, documentService, 3003);
    console.log('✓ WebServer instance');
    
    // Test that Discord client can be created (without connecting)
    console.log('\nTesting Discord client creation...');
    const client = new Client({
        intents: [
            GatewayIntentBits.Guilds,
            GatewayIntentBits.GuildMessages,
            GatewayIntentBits.MessageContent,
        ],
    });
    console.log('✓ Discord client created');
    
    console.log('\n=== All Syntax Tests Passed ===');
    console.log('✓ Bot code is syntactically correct');
    console.log('✓ All modules can be imported');
    console.log('✓ All services can be instantiated');
    console.log('\nNote: Bot is ready to start. Connect to Discord to begin.');
    
    // Cleanup
    webServer.stop().then(() => {
        setTimeout(() => process.exit(0), 1000);
    });
    
} catch (error) {
    console.error('\n✗ Error:', error.message);
    console.error('Stack:', error.stack);
    errors.push(error);
    process.exit(1);
}

