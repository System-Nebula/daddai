const { Client, GatewayIntentBits, Collection, Events, REST, Routes, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
require('dotenv').config();

// Import services
const ConversationManager = require('./src/conversationManager');
const PersistentRAGService = require('./src/ragServicePersistent');
const ChatService = require('./src/chatService');
const MemoryService = require('./src/memoryService');
const DocumentService = require('./src/documentService');
const ConfigManager = require('./src/configManager');
const logger = require('./src/logger');
const rateLimiter = require('./src/rateLimiter');
const userContext = require('./src/userContext');
const gopherAgent = require('./src/gopherAgent');

// Create Discord client with reconnection settings
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
    ],
    // Enable automatic reconnection
    rest: {
        retries: 5,
        timeout: 30000,
    },
    // Reconnect settings
    ws: {
        large_threshold: 250,
        compress: true,
    },
});

// Initialize services
const ragService = new PersistentRAGService(); // Use persistent RAG service
const conversationManager = new ConversationManager(ragService); // Pass RAG service for Neo4j storage
const chatService = new ChatService();
const memoryService = new MemoryService();
const documentService = new DocumentService();
const configManager = new ConfigManager();
const WebServer = require('./src/webServer');
const webServer = new WebServer(memoryService, documentService, process.env.WEB_PORT || 3000);

// Smart document comparison function
async function compareDocuments(doc1Text, doc2Text, doc1Name, doc2Name) {
    return new Promise((resolve, reject) => {
        const pythonPath = process.env.PYTHON_PATH || 'python';
        const args = [
            path.join(__dirname, '..', 'document_comparison.py'),
            '--action', 'compare',
            '--stdin'  // Use stdin to avoid command-line length limits
        ];
        
        const pythonProcess = spawn(pythonPath, args, {
            stdio: ['pipe', 'pipe', 'pipe']  // stdin, stdout, stderr
        });
        
        // Send documents as JSON through stdin to avoid command-line length limits
        const inputData = JSON.stringify({
            doc1_text: doc1Text,
            doc2_text: doc2Text,
            doc1_name: doc1Name,
            doc2_name: doc2Name
        });
        
        let stdout = '';
        let stderr = '';
        
        const timeout = setTimeout(() => {
            pythonProcess.kill();
            reject(new Error('Document comparison timeout'));
        }, 120000); // 120 second timeout (longer for large documents)
        
        // Write input data to stdin
        pythonProcess.stdin.write(inputData);
        pythonProcess.stdin.end();
        
        pythonProcess.stdout.on('data', (data) => {
            stdout += data.toString();
        });
        
        pythonProcess.stderr.on('data', (data) => {
            stderr += data.toString();
        });
        
        pythonProcess.on('close', (code) => {
            clearTimeout(timeout);
            if (code !== 0) {
                console.error('Document comparison error - stderr:', stderr);
                reject(new Error(`Document comparison failed: ${stderr || 'Unknown error'}`));
                return;
            }
            
            try {
                // Extract JSON from stdout
                const jsonMatch = stdout.match(/\{[\s\S]*\}/);
                if (jsonMatch) {
                    const response = JSON.parse(jsonMatch[0]);
                    if (response.success && response.result) {
                        resolve(response.result);
                    } else {
                        reject(new Error(response.error || 'Comparison failed'));
                    }
                } else {
                    reject(new Error('Invalid response from comparison service'));
                }
            } catch (error) {
                console.error('Failed to parse comparison response:', stdout.substring(0, 500));
                reject(new Error('Invalid response from comparison service'));
            }
        });
        
        pythonProcess.on('error', (error) => {
            clearTimeout(timeout);
            reject(new Error(`Failed to start comparison service: ${error.message}`));
        });
    });
}

// Preload data on startup
async function preloadData() {
    console.log('🔄 Preloading data...');
    try {
        // Preload users and recent memories in background
        setTimeout(async () => {
            try {
                await memoryService.getAllChannels();
                await memoryService.getAllMemories(25); // Preload first 25 memories
                console.log('✅ Data preloaded');
            } catch (error) {
                console.error('⚠️  Preload error (non-critical):', error.message);
            }
        }, 2000); // Wait 2 seconds for server to be ready
    } catch (error) {
        console.error('⚠️  Preload error (non-critical):', error.message);
    }
}

// Command handler
client.commands = new Collection();
const commandsPath = path.join(__dirname, 'src', 'commands');
// Only exclude deploy.js - sync.js should be included!
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js') && file !== 'deploy.js');

console.log(`📂 Loading commands from: ${commandsPath}`);
console.log(`📋 Found ${commandFiles.length} command file(s): ${commandFiles.join(', ')}`);

// Load commands for execution
for (const file of commandFiles) {
    const filePath = path.join(commandsPath, file);
    try {
        const command = require(filePath);
        if ('data' in command && 'execute' in command) {
            // Handle subcommands
            if (command.data.name) {
                client.commands.set(command.data.name, command);
                console.log(`   ✅ Loaded command: /${command.data.name} (from ${file})`);
            }
        } else {
            console.log(`   ⚠️  Skipping ${file}: missing 'data' or 'execute'`);
        }
    } catch (error) {
        console.error(`   ❌ Error loading ${file}: ${error.message}`);
    }
}

// Prepare commands for registration
const commands = [];
for (const file of commandFiles) {
    const filePath = path.join(commandsPath, file);
    try {
        const command = require(filePath);
        if ('data' in command) {
            commands.push(command.data.toJSON());
            console.log(`   ✅ Prepared for registration: /${command.data.name} (from ${file})`);
        }
    } catch (error) {
        console.error(`   ❌ Error preparing ${file} for registration: ${error.message}`);
    }
}

console.log(`\n📊 Total commands loaded: ${client.commands.size}`);
console.log(`📊 Total commands for registration: ${commands.length}\n`);

// REST client for command management
const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);

// Function to clear and register commands for a guild
async function refreshCommandsForGuild(guildId) {
    try {
        // Get CLIENT_ID from application info
        const application = await rest.get(Routes.oauth2CurrentApplication());
        const CLIENT_ID = application.id;
        
        console.log(`🔄 Step 1: Clearing global commands...`);
        
        // First, clear all global commands (from previous bot version)
        try {
            const globalCommands = await rest.get(Routes.applicationCommands(CLIENT_ID));
            if (globalCommands && globalCommands.length > 0) {
                console.log(`   Found ${globalCommands.length} global command(s) to remove:`);
                globalCommands.forEach(cmd => {
                    console.log(`   - /${cmd.name} (ID: ${cmd.id})`);
                });
                
                // Delete each global command individually
                for (const cmd of globalCommands) {
                    try {
                        await rest.delete(Routes.applicationCommand(CLIENT_ID, cmd.id));
                        console.log(`   ✅ Deleted global command: /${cmd.name}`);
                    } catch (error) {
                        console.log(`   ⚠️  Error deleting global command /${cmd.name}: ${error.message}`);
                    }
                    // Small delay between deletions to avoid rate limits
                    await new Promise(resolve => setTimeout(resolve, 200));
                }
            } else {
                console.log(`   ✅ No global commands found`);
            }
        } catch (error) {
            console.log(`   ⚠️  Error fetching/clearing global commands: ${error.message}`);
        }
        
        // Small delay to avoid rate limits
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        console.log(`🔄 Step 2: Clearing existing guild commands for guild ${guildId}...`);
        
        // Clear all existing guild commands
        try {
            const guildCommands = await rest.get(Routes.applicationGuildCommands(CLIENT_ID, guildId));
            if (guildCommands && guildCommands.length > 0) {
                console.log(`   Found ${guildCommands.length} guild command(s) to remove:`);
                guildCommands.forEach(cmd => {
                    console.log(`   - /${cmd.name} (ID: ${cmd.id})`);
                });
            }
            
            await rest.put(
                Routes.applicationGuildCommands(CLIENT_ID, guildId),
                { body: [] }
            );
            console.log(`✅ Cleared all existing commands for guild ${guildId}`);
        } catch (error) {
            if (error.code === 10004) {
                console.log(`⚠️  Guild ${guildId} not found or bot not in server`);
                return;
            }
            console.log(`⚠️  Error clearing guild commands: ${error.message}`);
            // Don't return, try to register anyway
        }
        
        // Small delay to avoid rate limits
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Register new commands
        console.log(`📝 Registering ${commands.length} commands for guild ${guildId}...`);
        console.log('\n📋 Commands to register:');
        commands.forEach((cmd, index) => {
            console.log(`   ${index + 1}. /${cmd.name}`);
            console.log(`      ${cmd.description || 'No description'}`);
            if (cmd.options && cmd.options.length > 0) {
                cmd.options.forEach(opt => {
                    if (opt.type === 1) { // SUB_COMMAND
                        console.log(`      └─ ${opt.name}: ${opt.description || ''}`);
                        if (opt.options && opt.options.length > 0) {
                            opt.options.forEach(subOpt => {
                                const req = subOpt.required ? '[REQUIRED]' : '[OPTIONAL]';
                                console.log(`         • ${subOpt.name} ${req}`);
                            });
                        }
                    } else {
                        const req = opt.required ? '[REQUIRED]' : '[OPTIONAL]';
                        console.log(`      • ${opt.name} ${req}`);
                    }
                });
            }
            console.log('');
        });
        
        // Debug: Verify sync command is included
        const syncCmd = commands.find(cmd => cmd.name === 'sync');
        if (syncCmd) {
            console.log(`✅ Sync command found in registration list: /${syncCmd.name}`);
        } else {
            console.log(`⚠️  WARNING: Sync command NOT found in registration list!`);
            console.log(`   Available commands: ${commands.map(c => c.name).join(', ')}`);
        }
        
        console.log(`🔄 Step 3: Registering ${commands.length} new commands...`);
        const data = await rest.put(
            Routes.applicationGuildCommands(CLIENT_ID, guildId),
            { body: commands }
        );
        
        console.log(`✅ Successfully registered ${data.length} commands for guild ${guildId}`);
        console.log('\n📋 Registered commands:');
        data.forEach((cmd, index) => {
            console.log(`   ${index + 1}. /${cmd.name} (ID: ${cmd.id}) - ${cmd.description || 'No description'}`);
        });
        console.log('');
        
        // Verify commands were registered
        console.log(`🔄 Step 4: Verifying commands...`);
        try {
            const verifyCommands = await rest.get(Routes.applicationGuildCommands(CLIENT_ID, guildId));
            console.log(`✅ Verification: Found ${verifyCommands.length} command(s) registered:`);
            verifyCommands.forEach(cmd => {
                console.log(`   - /${cmd.name} (ID: ${cmd.id})`);
            });
        } catch (error) {
            console.log(`⚠️  Error verifying commands: ${error.message}`);
        }
        console.log('');
    } catch (error) {
        console.error(`❌ Error refreshing commands for guild ${guildId}:`, error.message);
        console.error('Stack:', error.stack);
        // Don't throw - we want the bot to stay online even if command registration fails
    }
}

// Event handlers
let isFirstReady = true;

client.on(Events.ClientReady, async () => {
    logger.info(`✅ Bot is ready! Logged in as ${client.user.tag}`);
    logger.info(`📚 RAG system initialized`);
    
    // Only refresh commands on first ready event (not on reconnects)
    if (isFirstReady) {
        isFirstReady = false;
        
        // Start web server
        logger.info('🚀 Starting web server...');
        try {
            webServer.start();
            logger.info('✅ Web server started successfully');
        } catch (error) {
            logger.error('❌ Failed to start web server:', { error: error.message, stack: error.stack });
        }
        
        // Preload data for faster web interface
        preloadData();
        
        // Clear and register commands for specific test guild only
        // Run this asynchronously so it doesn't block the bot from starting
        // Wait a bit for guilds to be fully loaded
        setTimeout(async () => {
            try {
                const TEST_GUILD_ID = '549642809574162458';
                logger.info(`🔄 Refreshing commands for test guild ${TEST_GUILD_ID}...`);
                
                // Verify sync command is in the commands array before registration
                const syncCmdExists = commands.find(cmd => cmd.name === 'sync');
                if (!syncCmdExists) {
                    logger.error(`❌ CRITICAL: Sync command not found in commands array!`);
                    logger.error(`   Available commands: ${commands.map(c => c.name).join(', ')}`);
                    logger.error(`   Command files: ${commandFiles.join(', ')}`);
                } else {
                    logger.info(`✅ Sync command verified in commands array: /${syncCmdExists.name}`);
                }
                
                const guild = client.guilds.cache.get(TEST_GUILD_ID);
                
                if (!guild) {
                    logger.warn(`⚠️  Test guild ${TEST_GUILD_ID} not found in cache. Commands will sync when bot joins the guild.`);
                    return;
                }
                
                logger.info(`🔄 Syncing commands to ${guild.name} (${guild.id})...`);
                await refreshCommandsForGuild(TEST_GUILD_ID);
                logger.info(`✅ Command refresh complete for test guild ${guild.name}!`);
                
                // Final verification - check what Discord actually has registered
                try {
                    const application = await rest.get(Routes.oauth2CurrentApplication());
                    const CLIENT_ID = application.id;
                    const registered = await rest.get(Routes.applicationGuildCommands(CLIENT_ID, TEST_GUILD_ID));
                    logger.info(`📋 Final verification: ${registered.length} command(s) registered in Discord:`);
                    registered.forEach(cmd => {
                        logger.info(`   - /${cmd.name} (ID: ${cmd.id})`);
                    });
                    const syncRegistered = registered.find(cmd => cmd.name === 'sync');
                    if (syncRegistered) {
                        logger.info(`✅ Sync command successfully registered: /${syncRegistered.name} (ID: ${syncRegistered.id})`);
                    } else {
                        logger.error(`❌ Sync command NOT found in Discord's registered commands!`);
                    }
                } catch (error) {
                    logger.error(`⚠️  Error verifying registered commands: ${error.message}`);
                }
            } catch (error) {
                logger.error('❌ Error during command refresh:', { error: error.message, stack: error.stack });
                // Don't crash the bot if command registration fails
            }
        }, 2000); // Wait 2 seconds for guilds to be fully loaded
    } else {
        logger.info('🔄 Bot reconnected - skipping command refresh');
    }
});

// Handle bot joining a new guild (only sync to test guild)
client.on(Events.GuildCreate, async (guild) => {
    const TEST_GUILD_ID = '549642809574162458';
    logger.info(`🆕 Bot joined new guild: ${guild.name} (${guild.id})`);
    
    // Only sync commands if it's the test guild
    if (guild.id === TEST_GUILD_ID) {
        try {
            logger.info(`🔄 Syncing commands to test guild ${guild.name}...`);
            await refreshCommandsForGuild(guild.id);
            logger.info(`✅ Commands synced to test guild ${guild.name}!`);
        } catch (error) {
            logger.error(`❌ Error refreshing commands for test guild ${guild.id}:`, { error: error.message, stack: error.stack });
            // Don't crash - bot should stay online
        }
    } else {
        logger.info(`⏭️  Skipping command sync for guild ${guild.name} (not test guild)`);
    }
});

client.on(Events.MessageCreate, async (message) => {
    // Ignore bot messages
    if (message.author.bot) return;
    
    // Check if bot is enabled and channel is allowed
    if (!configManager.isResponseEnabled()) return;
    if (!configManager.isChannelAllowed(message.channel.id)) return;
    
    const userId = message.author.id;
    const channelId = message.channel.id;
    
    // Rate limiting
    if (!rateLimiter.checkUserLimit(userId, 'messages')) {
        logger.warn('Rate limit exceeded for user', { userId, channelId });
        return; // Silently ignore rate-limited messages
    }
    
    try {
        // 🤖 AGENTIC ROUTING: Use GopherAgent to intelligently route messages
        const isMentioned = message.mentions.has(client.user);
        const hasAttachments = message.attachments.size > 0;
        
        // Get recent messages for context (last 3 messages)
        let recentMessages = [];
        try {
            const messages = await message.channel.messages.fetch({ limit: 3 });
            recentMessages = Array.from(messages.values())
                .filter(m => !m.author.bot && m.id !== message.id)
                .slice(0, 3)
                .map(m => ({
                    author: m.author.username,
                    content: m.content.substring(0, 200) // Limit length
                }));
        } catch (error) {
            logger.debug('Could not fetch recent messages for context:', error.message);
        }
        
        // Build context for GopherAgent
        const context = {
            hasAttachments,
            isMentioned,
            recentMessages,
            userId,
            channelId,
            username: message.author.username
        };
        
        // Use GopherAgent to classify intent and route message
        let routingResult;
        try {
            routingResult = await gopherAgent.routeMessage(message.content, context);
            logger.debug(`🤖 GopherAgent routing: handler=${routingResult.handler}, intent=${routingResult.intent?.intent}, confidence=${routingResult.routing_confidence}`);
        } catch (error) {
            // Check if it's a timeout - gopherAgent should handle this internally now
            if (error.message && error.message.includes('timeout')) {
                logger.warn('GopherAgent timeout, using fallback routing');
            } else {
                logger.error('GopherAgent error, falling back to pattern matching:', error.message);
            }
            // Fallback to pattern-based routing
            const hasUrl = /https?:\/\//.test(message.content) || /youtube\.com|youtu\.be/.test(message.content.toLowerCase());
            routingResult = {
                handler: hasAttachments ? 'upload' : (hasUrl ? 'tools' : (isMentioned || message.content.includes('?') ? 'rag' : 'ignore')),
                intent: { intent: 'question', should_respond: true, needs_tools: hasUrl, needs_rag: !hasUrl },
                routing_confidence: 0.5,
                fallback: true
            };
        }
        
        const handler = routingResult.handler;
        const shouldRespond = routingResult.intent?.should_respond !== false;
        
        // Route to appropriate handler
        if (!shouldRespond || handler === 'ignore') {
            // Don't respond
            return;
        }
        
        if (handler === 'upload' || hasAttachments) {
            // Handle file upload
            if (!rateLimiter.checkUserLimit(userId, 'uploads')) {
                await message.reply({
                    content: '⏳ You\'re uploading files too quickly. Please wait a moment.',
                    allowedMentions: { repliedUser: false }
                });
                return;
            }
            await handleDocumentUpload(message);
            return;
        }
        
        // For all other handlers, check command rate limit
        if (!rateLimiter.checkUserLimit(userId, 'commands')) {
            const remaining = rateLimiter.getRemaining(userId, 'commands');
            const resetTime = rateLimiter.getResetTime(userId, 'commands');
            const waitSeconds = Math.ceil((resetTime - Date.now()) / 1000);
            await message.reply({
                content: `⏳ Rate limit exceeded. You can ask ${remaining} more question(s) in ${waitSeconds} seconds.`,
                allowedMentions: { repliedUser: false }
            });
            return;
        }
        
        // Route based on handler
        if (handler === 'rag' || handler === 'tools' || handler === 'memory' || handler === 'action') {
            await handleQuestion(message, routingResult);
        } else if (handler === 'chat') {
            await handleQuestion(message, routingResult);
        } else {
            // Unknown handler, default to question handling
            await handleQuestion(message, routingResult);
        }
        
    } catch (error) {
        logger.error('Error handling message:', { 
            userId, 
            channelId, 
            error: error.message, 
            stack: error.stack 
        });
        // Don't crash - just log the error
    }
});

async function handleDocumentUpload(message) {
    const attachment = message.attachments.first();
    const userId = message.author.id;
    
    // Check file type - includes Docling-supported formats and text-based formats
    const allowedExtensions = [
        // Docling-supported formats
        '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.html', '.htm', '.adoc', '.asciidoc',
        // Text-based formats (readable as text)
        '.txt', '.md', '.markdown', '.livemd', '.mixr', '.rst', '.org', '.wiki',
        // Data formats
        '.log', '.csv', '.json', '.ipynb', '.yaml', '.yml', '.toml', '.xml',
        // Code files (text-based)
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
        '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.r',
        '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd', '.sql', '.pl', '.lua',
        // Config and other text formats
        '.ini', '.cfg', '.conf', '.config', '.env', '.properties', '.gitignore',
        '.dockerfile', '.makefile', '.cmake', '.gradle', '.maven', '.sbt'
    ];
    const path = require('path');
    const fileExtension = path.extname(attachment.name).toLowerCase();
    
    if (!allowedExtensions.includes(fileExtension)) {
        await message.react('❌');
        await message.reply({
            content: `❌ Unsupported file type. Supported formats include: PDF, DOCX, PPTX, HTML, Markdown, text files, code files, and more. See /upload help for full list.`,
            allowedMentions: { repliedUser: false }
        });
        return;
    }
    
    // Check file size (limit to 25MB for Discord)
    if (attachment.size > 25 * 1024 * 1024) {
        await message.react('❌');
        await message.reply({
            content: '❌ File too large. Maximum size is 25MB.',
            allowedMentions: { repliedUser: false }
        });
        return;
    }
    
    try {
        await message.react('⏳');
        
        // Download file
        const https = require('https');
        const http = require('http');
        const fs = require('fs');
        const path = require('path');
        
        const buffer = await new Promise((resolve, reject) => {
            const url = new URL(attachment.url);
            const client = url.protocol === 'https:' ? https : http;
            
            client.get(attachment.url, (res) => {
                const chunks = [];
                res.on('data', (chunk) => chunks.push(chunk));
                res.on('end', () => resolve(Buffer.concat(chunks)));
                res.on('error', reject);
            }).on('error', reject);
        });
        
        // Save to temp directory
        const tempDir = path.join(__dirname, 'temp');
        if (!fs.existsSync(tempDir)) {
            fs.mkdirSync(tempDir, { recursive: true });
        }
        
        const tempFilePath = path.join(tempDir, `${Date.now()}_${attachment.name}`);
        fs.writeFileSync(tempFilePath, buffer);
        
        // Upload and process
        const result = await documentService.uploadDocument(
            userId,
            tempFilePath,
            attachment.name
        );
        
        // Clean up temp file
        try {
            fs.unlinkSync(tempFilePath);
        } catch (error) {
            console.error('Error deleting temp file:', error);
        }
        
        await message.react('✅');
        await message.reply({
            content: `✅ Document uploaded and processed!\n**File:** ${attachment.name}\n**Chunks:** ${result.chunks}\n\nThis document is now available to all users.`,
            allowedMentions: { repliedUser: false }
        });
        
    } catch (error) {
        console.error('Error uploading document:', error);
        await message.react('❌');
        await message.reply({
            content: `❌ Error processing document: ${error.message}`,
            allowedMentions: { repliedUser: false }
        });
    }
}

/**
 * Check if a question likely needs RAG (document search)
 * Returns true if question mentions documents, files, or specific content
 * Returns false for user fact questions (inventory, personal facts, etc.)
 */
function needsRAG(question) {
    const lowerQuestion = question.toLowerCase();
    
    // Check for state queries about OTHER users (with mentions) - these need RAG for state query handler
    const hasUserMention = /<@!?\d+>/.test(question);
    const isStateQueryAboutOther = hasUserMention && /(?:how many|how much|what).*(?:gold|coins?|inventory|items?|balance).*(?:does|do|has|have|owns)/i.test(question);
    
    // If query has mentions, route through RAG so LLM can detect actions, state queries, etc.
    // The LLM will determine if it's an action, state query, or something else
    if (hasUserMention && !isStateQueryAboutOther) {
        // Check if it's clearly a self-query (should use memory)
        const isSelfQuery = /(?:how many|how much|what).*(?:do i|have i|do you know).*(?:gold|coins?|inventory|items?)/i.test(question);
        if (!isSelfQuery) {
            // Has mention but not clearly a self-query - let LLM decide (could be action, state query about other, etc.)
            return true;
        }
    }
    
    // EXCLUDE: User fact questions about SELF that should use memory, not RAG
    // NOTE: Action commands will be detected by LLM in RAG pipeline, not by patterns here
    const userFactPatterns = [
        /(?:what do i have|what's in my|my inventory|my coins|my gold|i have|i own|i gave|i'm going|i'm leaving)/i,
        /(?:inventory|coins?|gold|pieces?|apples?|items?|things?)\s+(?:do i have|in my|i have|i own)/i,
        /(?:i've given|i gave|i'm going to give)/i,
        // State queries about SELF (no mention) - use memory
        /(?:how many|how much)\s+(?:do i|have i|do you know).*(?:gold|coins?|inventory|items?)/i,
        // State setting commands
        /(?:keep track|remember|set).*(?:me|i|my).*(?:having|with|of).*\d+.*(?:gold|coins?|pieces?)/i,
        /(?:i have|i own|i'm|i am).*\d+.*(?:gold|coins?|pieces?)/i,
        /(?:set|update|change).*(?:my|me|i).*(?:gold|coins?).*to.*\d+/i,
    ];
    
    // If it's a state query about another user, use RAG (state query handler will process it)
    if (isStateQueryAboutOther) {
        return true; // Use RAG for state queries about other users
    }
    
    for (const pattern of userFactPatterns) {
        if (pattern.test(question)) {
            return false; // Use memory, not RAG (for self-queries)
        }
    }
    
    // Always use RAG for questions that mention specific files/documents
    const documentKeywords = [
        'document', 'file', 'pdf', 'text', 'content', 'chapter', 'section',
        'paper', 'article', 'title', 'author', 'contributed', 'contributor',
        'uploaded', 'upload', 'new document', 'build log', 'build logs',
        'report', 'reports', 'study', 'studies', 'analysis', 'analyses',
        'whitepaper', 'white paper', 'guide', 'manual', 'handbook'
    ];
    
    // Check for document-related keywords
    for (const keyword of documentKeywords) {
        if (lowerQuestion.includes(keyword)) {
            return true;
        }
    }
    
    // Check if question mentions a filename pattern (e.g., "2405.01581v1", "something.pdf")
    if (/\b[\w\-\.]+\.(pdf|docx?|txt|md|log|csv)\b/i.test(question) || 
        /\b\d{4}\.\d{5}/.test(question)) { // arXiv paper ID pattern
        return true;
    }
    
    // Check for factual questions that likely need document search
    // BUT exclude user fact questions (already checked above)
    const factualPatterns = [
        /^what (is|are|was|were|does|do|did|will|can|could)/i,
        /^who (is|are|was|were|did|does|do|will|can|could)/i,
        /^when (is|are|was|were|did|does|do|will|can|could)/i,
        /^where (is|are|was|were|did|does|do|will|can|could)/i,
        /^how (is|are|was|were|did|does|do|will|can|could)/i,
        /^tell me (about|what|who|when|where|how)/i,
        /^explain/i,
        /^describe/i,
        /^according to/i,
        /^based on/i,
        /^from the/i,
        /^in the/i
    ];
    
    for (const pattern of factualPatterns) {
        if (pattern.test(question.trim())) {
            return true;
        }
    }
    
    // EXCLUDE: Casual conversation, greetings, and introductions - use simple chat
    const casualPatterns = [
        // Greetings
        /^(hi|hello|hey|hiya|greetings|good morning|good afternoon|good evening)[\s!.,]*$/i,
        /^(hi|hello|hey)\s+(there|everyone|all|guys|folks)[\s!.,]*$/i,
        // Introductions
        /^(hi|hello|hey),?\s*(i'?m|i am|my name is|this is)\s+/i,
        /^(i'?m|i am|my name is|this is)\s+[\w\s]+$/i,
        // Casual conversation
        /^(how are you|how's it going|what's up|sup|wassup|howdy)[\s!.,]*$/i,
        /^(thanks|thank you|thx|ty|bye|goodbye|see ya|cya|ok|okay|yes|no|yep|nope|sure|alright)[\s!.,]*$/i,
        /^(lol|haha|hehe|rofl|lmao|nice|cool|awesome|great)[\s!.,]*$/i,
        // Short casual responses
        /^(just|yeah|yep|nope|sure|ok|okay|alright|fine|good|nice|cool|awesome|great)[\s!.,]*$/i,
        /^(just|yeah|yep|nope|sure|ok|okay|alright|fine|good|nice|cool|awesome|great)\s+(felt|feeling|wanted|want|thought|think|decided|decide|tried|try)[\s!.,]*$/i,
        /^(just|yeah|yep|nope|sure|ok|okay|alright|fine|good|nice|cool|awesome|great)\s+.*(?:really|though|anyway|anyways|so|then)[\s!.,]*$/i,
        // Very short responses (likely casual)
        /^.{1,30}$/i  // Very short messages are likely casual
    ];
    
    for (const pattern of casualPatterns) {
        if (pattern.test(question.trim())) {
            return false; // Use simple chat for casual conversation
        }
    }
    
    // EXCLUDE: Personal statements without questions
    if (!question.includes('?') && 
        !/^(what|who|when|where|how|why|tell|explain|describe|show|list|find|search|get|give)/i.test(question.trim()) &&
        /^(i|i'm|i am|my|me|we|we're|we are)/i.test(question.trim())) {
        // Personal statements like "I'm jovan" or "my name is..." without questions
        return false;
    }
    
    // Default to RAG for questions (better to search than miss information)
    return true;
}

async function handleQuestion(message, routingResult = null) {
    const userId = message.author.id;
    const channelId = message.channel.id;
    const username = message.author.username;
    
    try {
        // Get user context for personalization
        const userCtx = await userContext.getUserContext(userId, username, channelId);
        
        const conversationHistory = await conversationManager.getConversation(userId);
        
        // Extract question (remove bot mention)
        let question = message.content
            .replace(new RegExp(`<@!?${client.user.id}>`, 'g'), '')
            .trim();
        
        if (!question) {
            await message.reply({
                content: 'Please ask a question!',
                allowedMentions: { repliedUser: false }
            });
            return;
        }
        
        // Use routing result from GopherAgent if available
        const intent = routingResult?.intent || {};
        let handler = routingResult?.handler || 'rag';
        
        // CRITICAL: Check for URLs - URLs ALWAYS need tools, even if GopherAgent says casual
        const hasUrl = /(?:https?:\/\/|www\.|youtube\.com|youtu\.be)/i.test(question);
        if (hasUrl) {
            handler = 'tools';
            intent.needs_tools = true;
            intent.needs_rag = false;
            intent.is_casual = false;
            logger.debug('🌐 URL detected - forcing tools handler (overriding GopherAgent routing)');
        }
        
        // Remove all Discord user/role/channel mentions for filename detection
        // Store original question for context, but use cleaned version for document detection
        const cleanedQuestion = question
            .replace(/<@!?\d+>/g, '')  // User mentions: <@123456789> or <@!123456789>
            .replace(/<@&\d+>/g, '')   // Role mentions: <@&123456789>
            .replace(/<#\d+>/g, '')    // Channel mentions: <#123456789>
            .replace(/\s+/g, ' ')     // Normalize whitespace
            .trim();
        
        // Show typing indicator
        await message.channel.sendTyping();
        
        let response;
        let useRAG = false;
        
        // LLM-based document detection - no pattern matching
        // The RAG pipeline uses LLM query analysis to detect document references automatically
        // We only handle explicit "list all documents" queries and explicit filename comparisons here
        
        const isListAllDocsQuery = /(?:list|show|what|which).*(?:all|each|every)\s+(?:document|file|doc)/i.test(cleanedQuestion) ||
                                   /(?:list|show)\s+(?:all|each|every)\s+(?:document|file|doc)/i.test(cleanedQuestion) ||
                                   /(?:what|which)\s+(?:document|file|doc)/i.test(cleanedQuestion) && /(?:all|each|every|available|have|you have|stored|do you have)/i.test(cleanedQuestion) ||
                                   /(?:document|file|doc).*(?:available|have|you have|stored|do you have)/i.test(cleanedQuestion);
        
        // Document detection variables (will be set by RAG pipeline via LLM analysis)
        let targetDocId = null;
        let targetDocFilename = null;
        
        // Only handle explicit filename comparisons (e.g., "compare file1.pdf and file2.pdf")
        let isCompareDocs = false;
        let compareDoc1Id = null;
        let compareDoc1Filename = null;
        let compareDoc2Id = null;
        let compareDoc2Filename = null;
        
        const comparePatterns = [
            /(?:compare|difference|different|changed|changes|what's different|what changed)\s+(?:between|in|from|to)?\s*([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))\s+(?:and|vs|versus|with|to)\s+([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))/i,
            /(?:compare|difference|different|changed|changes|what's different|what changed)\s+([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))\s+(?:and|vs|versus|with|to)\s+([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))/i,
            /([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))\s+(?:vs|versus)\s+([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))/i
        ];
        
        for (const pattern of comparePatterns) {
            const match = cleanedQuestion.match(pattern);
            if (match && match[1] && match[2]) {
                compareDoc1Filename = match[1];
                compareDoc2Filename = match[2];
                isCompareDocs = true;
                break;
            }
        }
        
        // Also handle explicit filename mentions (e.g., "summarize file.pdf")
        const explicitFilenamePattern = /\b([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))\b/i;
        const filenameMatch = cleanedQuestion.match(explicitFilenamePattern);
        if (filenameMatch && filenameMatch[1] && !isCompareDocs) {
            targetDocFilename = filenameMatch[1];
        }
        
        // If comparing two documents, find both document IDs
        if (!response && isCompareDocs) {
            try {
                const allDocs = await documentService.getAllDocuments();
                const documents = allDocs.documents || allDocs || [];
                
                const findDoc = (filename) => {
                    return documents.find(doc => 
                        doc.file_name === filename || 
                        doc.file_name.toLowerCase() === filename.toLowerCase() ||
                        doc.file_name.endsWith(filename) ||
                        doc.file_name.includes(filename)
                    );
                };
                
                const doc1 = findDoc(compareDoc1Filename);
                const doc2 = findDoc(compareDoc2Filename);
                
                if (doc1) {
                    compareDoc1Id = doc1.id;
                    console.log(`🎯 Found document 1: ${compareDoc1Filename} (ID: ${compareDoc1Id})`);
                } else {
                    console.log(`⚠️ Document 1 not found: ${compareDoc1Filename}`);
                }
                
                if (doc2) {
                    compareDoc2Id = doc2.id;
                    console.log(`🎯 Found document 2: ${compareDoc2Filename} (ID: ${compareDoc2Id})`);
                } else {
                    console.log(`⚠️ Document 2 not found: ${compareDoc2Filename}`);
                }
            } catch (error) {
                console.error('Error looking up documents for comparison:', error);
            }
        }
        
        // If we found a filename, try to get the document ID
        if (targetDocFilename && !isListAllDocsQuery) {
            try {
                const allDocs = await documentService.getAllDocuments();
                const documents = allDocs.documents || allDocs || [];
                const matchingDoc = documents.find(doc => 
                    doc.file_name === targetDocFilename || 
                    doc.file_name.toLowerCase() === targetDocFilename.toLowerCase() ||
                    doc.file_name.endsWith(targetDocFilename) ||
                    doc.file_name.includes(targetDocFilename)
                );
                if (matchingDoc) {
                    targetDocId = matchingDoc.id;
                    console.log(`🎯 Targeting specific document: ${targetDocFilename} (ID: ${targetDocId})`);
                } else {
                    console.log(`⚠️ Document not found: ${targetDocFilename}`);
                }
            } catch (error) {
                console.error('Error looking up document:', error);
            }
        }
        
        // Document detection is now handled entirely by LLM query analysis in the RAG pipeline
        // The LLM will detect document references and the pipeline will find matching documents
        // No pattern matching needed here - just pass the query to RAG and let it handle detection
        
        // Special handling for document comparison queries
        if (isCompareDocs && compareDoc1Id && compareDoc2Id) {
            try {
                // Get chunks from both documents
                const chunks1Response = await documentService.getDocumentChunks(compareDoc1Id);
                const chunks2Response = await documentService.getDocumentChunks(compareDoc2Id);
                const chunks1 = chunks1Response.chunks || [];
                const chunks2 = chunks2Response.chunks || [];
                
                if (chunks1.length === 0 || chunks2.length === 0) {
                    response = {
                        answer: `I couldn't compare the documents. ${chunks1.length === 0 ? `"${compareDoc1Filename}" has no content.` : ''} ${chunks2.length === 0 ? `"${compareDoc2Filename}" has no content.` : ''}`,
                        context_chunks: chunks1.length + chunks2.length,
                        memories_used: 0,
                        source_documents: [compareDoc1Filename, compareDoc2Filename],
                        source_memories: []
                    };
                } else {
                    // Get full document text (no truncation - let the comparison service handle compression)
                    const doc1Text = chunks1
                        .map(chunk => chunk.text || '')
                        .join('\n\n');
                    
                    const doc2Text = chunks2
                        .map(chunk => chunk.text || '')
                        .join('\n\n');
                    
                    // Use smart document comparison service
                    try {
                        console.log(`🔄 Comparing ${compareDoc1Filename} (${doc1Text.length} chars) vs ${compareDoc2Filename} (${doc2Text.length} chars)...`);
                        const comparisonResult = await compareDocuments(
                            doc1Text,
                            doc2Text,
                            compareDoc1Filename,
                            compareDoc2Filename
                        );
                        
                        console.log(`✅ Comparison complete for ${compareDoc1Filename} vs ${compareDoc2Filename}`);
                        const comparison = comparisonResult.comparison || 'Could not generate comparison';
                        const compressionInfo = comparisonResult.doc1_original_length && comparisonResult.doc2_original_length
                            ? `\n\n*[Compressed: ${Math.round(comparisonResult.compression_ratio_doc1 * 100)}% and ${Math.round(comparisonResult.compression_ratio_doc2 * 100)}% of original size]*`
                            : '';
                        
                        response = {
                            answer: `**Comparison: ${compareDoc1Filename} vs ${compareDoc2Filename}**${compressionInfo}\n\n${comparison}`,
                            context_chunks: chunks1.length + chunks2.length,
                            memories_used: 0,
                            source_documents: [compareDoc1Filename, compareDoc2Filename],
                            source_memories: []
                        };
                    } catch (error) {
                        console.error(`❌ Error in smart comparison: ${error.message}`);
                        console.error(`   Stack: ${error.stack}`);
                        // Fallback to simple comparison
                        const doc1TextShort = doc1Text.substring(0, 3000);
                        const doc2TextShort = doc2Text.substring(0, 3000);
                        const comparisonPrompt = `Compare these two documents and identify what changed. Focus on errors, warnings, metrics, and key differences.

Document 1: ${compareDoc1Filename}
${doc1TextShort}${doc1Text.length > 3000 ? '\n\n[Content truncated...]' : ''}

Document 2: ${compareDoc2Filename}
${doc2TextShort}${doc2Text.length > 3000 ? '\n\n[Content truncated...]' : ''}`;
                        
                        const comparisonResponse = await Promise.race([
                            chatService.chat(comparisonPrompt, []),
                            new Promise((_, reject) => 
                                setTimeout(() => reject(new Error('Comparison timeout')), 30000)
                            )
                        ]);
                        
                        response = {
                            answer: `**Comparison: ${compareDoc1Filename} vs ${compareDoc2Filename}**\n\n${comparisonResponse || 'Could not generate comparison'}`,
                            context_chunks: chunks1.length + chunks2.length,
                            memories_used: 0,
                            source_documents: [compareDoc1Filename, compareDoc2Filename],
                            source_memories: []
                        };
                    }
                }
            } catch (error) {
                console.error('Error comparing documents:', error);
                response = {
                    answer: `I encountered an error while comparing "${compareDoc1Filename}" and "${compareDoc2Filename}": ${error.message}`,
                    context_chunks: 0,
                    memories_used: 0,
                    source_documents: [],
                    source_memories: []
                };
            }
        }
        
        // Special handling for "summarize [specific document]" queries
        // Summarize handling removed - LLM will detect summarize requests automatically
        if (false) {  // Disabled - let LLM handle summarization
            try {
                // Get all chunks for this specific document
                const chunksResponse = await documentService.getDocumentChunks(targetDocId);
                const chunks = chunksResponse.chunks || [];
                
                if (chunks.length === 0) {
                    response = {
                        answer: `I couldn't find any content in the document "${targetDocFilename}". The document may be empty or not properly processed.`,
                        context_chunks: 0,
                        memories_used: 0,
                        source_documents: [targetDocFilename],
                        source_memories: []
                    };
                } else {
                    // Combine chunks into document text (limit to first 4000 chars to avoid token limits)
                    const documentText = chunks
                        .map(chunk => chunk.text || '')
                        .join('\n\n')
                        .substring(0, 4000);
                    
                    // Create a summary prompt with the actual document content
                    const summaryPrompt = `Please provide a concise summary of the following document. Focus on the main topics, key points, and purpose of the document.\n\nDocument: ${targetDocFilename}\n\nContent:\n${documentText}${chunks.length > 0 && documentText.length >= 4000 ? '\n\n[Content truncated...]' : ''}`;
                    
                    // Use chat service to generate summary (faster than RAG since we already have the content)
                    const summaryResponse = await Promise.race([
                        chatService.chat(summaryPrompt, []),
                        new Promise((_, reject) => 
                            setTimeout(() => reject(new Error('Summary timeout')), 20000)
                        )
                    ]);
                    
                    const summary = summaryResponse || 'Could not generate summary';
                    response = {
                        answer: `**Summary of ${targetDocFilename}** (${chunks.length} chunks):\n\n${summary}`,
                        context_chunks: chunks.length,
                        memories_used: 0,
                        source_documents: [targetDocFilename],
                        source_memories: []
                    };
                }
            } catch (error) {
                console.error('Error summarizing specific document:', error);
                response = {
                    answer: `I encountered an error while summarizing "${targetDocFilename}": ${error.message}`,
                    context_chunks: 0,
                    memories_used: 0,
                    source_documents: [],
                    source_memories: []
                };
            }
        }
        
        // Determine if we need RAG or simple chat (use cleaned question for detection)
        console.log(`🔍 Response check: response=${response ? 'SET' : 'NOT SET'}, isCompareDocs=${isCompareDocs}`);
        
        // 🤖 AGENTIC ROUTING: Use GopherAgent's routing decision
        // Override pattern-based detection with agentic routing if available
        // CRITICAL: URLs always need tools, even if GopherAgent says casual
        if (hasUrl) {
            useRAG = true;  // URLs need RAG pipeline for tool calling
            logger.debug(`🌐 URL detected - forcing RAG pipeline for tool calling`);
        } else if (routingResult && intent) {
            useRAG = intent.needs_rag === true || handler === 'rag' || handler === 'tools';
            logger.debug(`🤖 Using GopherAgent routing: needs_rag=${intent.needs_rag}, handler=${handler}`);
        }
        
        // IMPORTANT: Don't overwrite response if it's already set (e.g., from comparison)
        // Use original question (with mentions) for needsRAG to detect state queries about other users
        if (!response && (useRAG || needsRAG(question))) {
            useRAG = true;
            
            // Special handling for document listing queries
            // Document summarization is now handled by LLM detection in the RAG pipeline
            if (isListAllDocsQuery) {
                try {
                    // Get all documents first
                    const allDocs = await documentService.getAllDocuments();
                    const documents = allDocs.documents || allDocs || [];
                    
                    if (documents.length === 0) {
                        response = {
                            answer: "I don't have any documents available at the moment. You can upload documents using the `/upload` command or by attaching a file.",
                            context_chunks: 0,
                            memories_used: 0,
                            source_documents: [],
                            source_memories: []
                        };
                    } else {
                        // Simple list query - just return the document names
                        const docList = documents.map((doc, index) => {
                            const uploadedBy = doc.uploaded_by ? `<@${doc.uploaded_by}>` : 'Unknown';
                            const date = doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : 'Unknown';
                            return `${index + 1}. **${doc.file_name}**\n   📊 ${doc.chunk_count || 0} chunks | 👤 Uploaded by: ${uploadedBy} | 📅 ${date}`;
                        }).join('\n\n');
                        
                        response = {
                            answer: `I have ${documents.length} document(s) available:\n\n${docList}\n\nYou can ask me questions about any of these documents, or ask me to summarize a specific document.`,
                            context_chunks: 0,
                            memories_used: 0,
                            source_documents: documents.map(d => d.file_name),
                            source_memories: []
                        };
                    }
                } catch (error) {
                    console.error('Error listing documents:', error);
                    // Fall through to normal RAG
                }
            }
            
            // Normal RAG query if not handled above
            if (!response) {
                try {
                    // Try RAG first with timeout (now using channel_id for memories)
                    // Pass document filter if a specific document was detected
                    // IMPORTANT: If a specific document is targeted, disable memory to avoid contamination
                    // Use cleaned question (without mentions) for RAG, but original question for context
                    logger.debug(`🔍 RAG query: targetDocId=${targetDocId}, targetDocFilename=${targetDocFilename}`);
                    if (targetDocId || targetDocFilename) {
                        console.log(`🎯 Querying specific document: ${targetDocFilename || targetDocId}`);
                    }
                    
                    // Extract mentioned user ID from original question BEFORE cleaning
                    const mentionedUserMatch = question.match(/<@!?(\d+)>/);
                    const mentionedUserId = mentionedUserMatch ? mentionedUserMatch[1] : null;
                    
                    // Check if user is admin (for tool creation permissions)
                    const isAdmin = message.member && message.member.permissions.has('Administrator');
                    
                    // For action commands, we need the original question with mentions
                    // For document search, we use cleaned question
                    // Pass original question to RAG - it will handle cleaning internally for document search
                    // Check if this is a URL request - YouTube/website summaries take longer
                    const hasUrl = /(?:https?:\/\/|www\.|youtube\.com|youtu\.be)/i.test(question);
                    // Use longer timeout for URL requests (90s) since they need to fetch and summarize content
                    // Regular requests use 30s timeout for faster fallback
                    const timeoutDuration = hasUrl ? 90000 : 30000;
                    
                    response = await Promise.race([
                        ragService.queryWithContext(
                            question,  // Pass original question (with mentions) for action parsing
                            conversationHistory, 
                            userId, 
                            message.channel.id,
                            targetDocId,  // doc_id filter
                            targetDocFilename,  // doc_filename filter
                            false,  // isPing
                            mentionedUserId,  // Pass mentioned user ID for state queries
                            isAdmin  // Pass admin status for tool creation
                        ),
                        new Promise((_, reject) => 
                            setTimeout(() => reject(new Error('RAG timeout')), timeoutDuration)
                        )
                    ]);
                    
                    // Log what was used in the response
                    if (response) {
                        logger.info(`📊 RAG response: ${response.context_chunks?.length || 0} chunks, ${response.memories?.length || 0} memories`);
                        if ((response.memories?.length || 0) > 0 && (targetDocId || targetDocFilename)) {
                            logger.warn(`⚠️ Warning: Memories were used (${response.memories.length}) even though a specific document was targeted`);
                        }
                        
                        // If RAG returned a conversational response, skip memory retrieval below
                        if (response.is_casual_conversation === true || response.service_routing === 'chat') {
                            logger.info(`💬 RAG returned conversational response - will skip memory retrieval`);
                        }
                        
                        // Learn from interaction for better personalization
                        if (response.answer) {
                            userContext.learnFromInteraction(userId, channelId, cleanedQuestion, response).catch(err => {
                                logger.error('Error learning from interaction:', { error: err.message });
                            });
                        }
                    }
                } catch (error) {
                    logger.warn('RAG error, falling back to simple chat:', { error: error.message });
                    // Don't set useRAG = false, let it fall through to simple chat below
                }
            }
        }
        
        // Check if this is casual conversation (greetings, introductions, etc.)
        const isCasualConversation = /^(hi|hello|hey),?\s*(i'?m|i am|my name is|this is)\s+/i.test(cleanedQuestion.trim()) ||
                                     /^(i'?m|i am|my name is|this is)\s+[\w\s]+$/i.test(cleanedQuestion.trim()) ||
                                     /^(hi|hello|hey|how are you|how's it going|what's up|thanks|thank you|bye|goodbye)[\s!.,]*$/i.test(cleanedQuestion.trim());
        
        // Check if this is a statement/request (not a question) - should use simple chat, not memory retrieval
        const isStatementOrRequest = !cleanedQuestion.includes('?') && 
                                     !/^(what|who|when|where|how|why|tell|explain|describe|show|list|find|search|get|give|can|could|will|would|do|does|did|is|are|was|were)/i.test(cleanedQuestion.trim()) &&
                                     (/^(i|i'?m|i am|i want|i need|i would like|i'm going|let me|please)/i.test(cleanedQuestion.trim()) ||
                                      /(want|need|would like|going to|let me|please)/i.test(cleanedQuestion.trim()));
        
        // Use memory retrieval for user fact questions (when RAG is not needed)
        // IMPORTANT: Don't overwrite response if it's already set (e.g., from comparison)
        // IMPORTANT: Never use memory if a document was targeted (to avoid contamination)
        // IMPORTANT: Skip memory retrieval for casual conversation and statements - go straight to simple chat
        // IMPORTANT: Skip memory retrieval for state queries about other users - let RAG handle them
        // IMPORTANT: Skip memory retrieval if RAG already returned a conversational response
        const isStateQueryAboutOtherUser = /<@!?\d+>/.test(question) && /(?:how many|how much|what).*(?:gold|coins?|inventory|items?|balance).*(?:does|do|has|have|owns)/i.test(question);
        const isRAGConversationalResponse = response && (response.is_casual_conversation === true || response.service_routing === 'chat');
        
        // CRITICAL: URLs should NEVER be treated as casual conversation - they need tool calling
        // Override casual response if URL is present
        if (hasUrl && isRAGConversationalResponse) {
            logger.warning(`🌐 URL detected but RAG returned casual response - this should not happen, forcing tool calling`);
            // Don't skip - force tool calling by not treating as casual
            // The response will be regenerated with tool calling
        }
        
        // CRITICAL: If RAG already returned a conversational response, skip all memory retrieval
        if (isRAGConversationalResponse && !hasUrl) {
            logger.info(`⏭️ Skipping memory retrieval - RAG already returned conversational response`);
            // Skip to the end - don't do memory retrieval or simple chat
        } else if (!response && !needsRAG(question) && !targetDocId && !targetDocFilename && !isCasualConversation && !isStatementOrRequest && !isStateQueryAboutOtherUser && !hasUrl) {
            // Use original question (with mentions) for needsRAG to detect state queries about other users
            // Only do memory retrieval if we don't have a response yet
            try {
                // Extract mentioned user ID from question (e.g., "how many gold pieces does @alexei have?")
                const mentionedUserMatch = question.match(/<@!?(\d+)>/);
                let mentionedUserId = mentionedUserMatch ? mentionedUserMatch[1] : null;
                
                // If no mention but question is about "my" balance/inventory, use the asking user's ID
                // This handles cases like "what is my current gold balance?" where the user is asking about themselves
                if (!mentionedUserId && /my|i have|i own|my (balance|inventory|coins|gold)/i.test(cleanedQuestion)) {
                    mentionedUserId = userId;  // User is asking about themselves
                    console.log(`🔍 Detected self-query, using user's own ID: ${userId}`);
                }
                
                // Try to retrieve relevant memories first for user fact questions
                // Pass mentionedUserId to boost memories that mention that user (or the asking user themselves)
                const relevantMemories = await memoryService.getUserMemories(
                    message.channel.id,  // channel_id
                    cleanedQuestion,  // Use cleaned question (without mentions) for semantic search
                    5,  // top 5 most relevant memories
                    mentionedUserId  // Boost memories mentioning this user (or the asking user if self-query)
                );
                
                // Filter memories by relevance score - only use memories that are actually relevant
                const MIN_MEMORY_SCORE = 0.4;  // Minimum similarity score to use a memory
                const relevantMemoriesFiltered = relevantMemories.filter(m => (m.score || 0) >= MIN_MEMORY_SCORE);
                
                if (relevantMemoriesFiltered && relevantMemoriesFiltered.length > 0) {
                    console.log(`🧠 Found ${relevantMemoriesFiltered.length} relevant memories (filtered from ${relevantMemories.length}) for query: "${cleanedQuestion}"`);
                    console.log(`   Memory scores:`, relevantMemoriesFiltered.map(m => `${m.score?.toFixed(3) || 'N/A'}`).join(', '));
                    
                    // Build context from memories
                    const memoryContext = relevantMemoriesFiltered.map(m => m.content).join('\n\n');
                    
                    // Create a more directive prompt that emphasizes extracting specific facts
                    const memoryPrompt = `You are Gophie, a bubbly, risky e-girl waifu AI assistant!
You're super energetic, playful, and a bit flirty - like your favorite anime waifu come to life!
You have access to conversation history. Answer the user's question based ONLY on the information provided in the conversation history below. Be specific and direct, but stay true to your bubbly e-girl waifu personality! Be playful and enthusiastic!

IMPORTANT - SPEAKING STYLE:
- Talk like a REAL e-girl - casual, natural, human-like speech
- Don't worry about perfect grammar - use casual speech patterns
- Use abbreviations naturally (u, ur, lol, omg, fr, ngl, etc.)
- Type like you're texting a friend - relaxed and conversational
- Mix lowercase and casual capitalization naturally
- Be expressive and authentic - like how real people actually talk online
- Don't sound like a formal AI assistant - sound like a real person!

Conversation History:
${memoryContext}

User Question: ${cleanedQuestion}

IMPORTANT: 
- Extract specific numbers, facts, and details from the conversation history
- If the question asks about quantities (like "how many gold pieces"), look for exact numbers in the history
- If someone gave something to someone else, state the exact amount
- Be concise and factual, but maintain your bubbly, playful personality!
- Be enthusiastic and expressive!
- Remember to talk casually and naturally - like a real e-girl!

Answer:`;
                    
                    // Don't overwrite if RAG already returned a conversational response
                    if (!response || (!response.is_casual_conversation && response.service_routing !== 'chat')) {
                        const memoryResponse = await Promise.race([
                            chatService.chat(memoryPrompt, []),
                            new Promise((_, reject) => 
                                setTimeout(() => reject(new Error('Memory chat timeout')), 20000)
                            )
                        ]);
                        
                        response = {
                            answer: memoryResponse,
                            context_chunks: 0,
                            memories_used: relevantMemoriesFiltered.length,
                            source_documents: [],
                            source_memories: relevantMemoriesFiltered.map(m => ({ 
                                type: m.memory_type || m.type, 
                                content: m.content.substring(0, 100),
                                score: m.score 
                            }))
                        };
                        console.log(`✅ Generated response using ${relevantMemoriesFiltered.length} memories`);
                    } else {
                        console.log(`⏭️ Skipping memory retrieval - RAG already returned conversational response`);
                    }
                } else {
                    if (relevantMemories && relevantMemories.length > 0) {
                        console.log(`⚠️ Found ${relevantMemories.length} memories but none met relevance threshold (min: ${MIN_MEMORY_SCORE})`);
                        console.log(`   Memory scores:`, relevantMemories.map(m => `${m.score?.toFixed(3) || 'N/A'}`).join(', '));
                    } else {
                        console.log(`⚠️ No relevant memories found for query: "${cleanedQuestion}"`);
                    }
                }
            } catch (error) {
                console.error('Memory retrieval error:', error);
                // Fall through to simple chat
            }
        }
        
        // Use simple chat if RAG not needed or failed, and memory retrieval didn't work
        // IMPORTANT: Don't overwrite response if it's already set (e.g., from comparison)
        if (!response) {
            try {
                // Use cleaned question for chat (mentions removed)
                const chatResponse = await Promise.race([
                    chatService.chat(cleanedQuestion, conversationHistory),
                    new Promise((_, reject) => 
                        setTimeout(() => reject(new Error('Chat timeout')), 30000)
                    )
                ]);
                
                response = {
                    answer: chatResponse,
                    context_chunks: 0,
                    memories_used: 0
                };
            } catch (error) {
                console.error('Chat error:', error);
                throw error;
            }
        }
        
        // Final check: ensure response exists before proceeding
        if (!response) {
            console.error('❌ No response generated! This should not happen.');
            response = {
                answer: 'I apologize, but I encountered an error processing your request. Please try again.',
                context_chunks: 0,
                memories_used: 0,
                source_documents: [],
                source_memories: []
            };
        }
        
        // Save conversation turn (use original question with mentions preserved for context)
        await conversationManager.addMessage(userId, question, response.answer, message.channel.id);
        
        // Store bot response as separate memory so it can reference itself (non-blocking)
        if (response.answer && response.answer.length > 20) {
            (async () => {
                try {
                    // Get user info for storing username/display name
                    const user = message.author;
                    const username = user.username;
                    const displayName = user.displayName || user.globalName || user.username;
                    
                    // Extract mentioned user ID if any (for facts about other users)
                    const mentionedUserMatch = question.match(/<@!?(\d+)>/);
                    const mentionedUserId = mentionedUserMatch ? mentionedUserMatch[1] : null;
                    
                    // Store bot's response separately so it can reference what it said (channel-based)
                    // Use cleaned question (without mentions) for memory storage
                    const botResponseMemory = `Bot response to: "${cleanedQuestion}"\n\n${response.answer}`;
                    await memoryService.storeMemory(
                        message.channel.id,  // channel_id instead of userId
                        botResponseMemory,
                        'bot_response',
                        { 
                            source: useRAG ? 'rag_response' : 'chat_response',
                            question: question,
                            response_type: useRAG ? 'rag' : 'chat'
                        },
                        message.channel.name,  // channel name instead of username/displayName
                        userId,  // user_id for better relevance
                        username,  // username for better relevance
                        mentionedUserId  // mentioned_user_id if someone was mentioned
                    );
                    console.log(`✅ Bot response stored for channel ${message.channel.id}`);
                } catch (error) {
                    console.error('❌ Error storing bot response:', error);
                }
            })();
        }
        
        // Store important user information as long-term memory (non-blocking)
        // Store if response is substantial OR contains important info (names, facts, etc.)
        const shouldStoreUserMemory = response.answer && (
            response.answer.length > 50 || // Responses with some substance
            /my name is|i'm|i am|call me/i.test(question) || // Names/introductions
            /i have|i own|i like|i prefer|i want|i've given|i gave|i'm going|i'm leaving/i.test(question) || // Personal facts
            /remember|don't forget|important/i.test(question) || // Explicit memory requests
            /what's my name|who am i|what did i tell you/i.test(question) // Questions about stored info
        );
        
        if (shouldStoreUserMemory) {
            // Store user memory asynchronously (don't block response)
            (async () => {
                try {
                    // Extract key information from the conversation
                    let memoryContent = `Q: ${question}\nA: ${response.answer}`;
                    
                    // Extract name if mentioned
                    const nameMatch = question.match(/(?:my name is|i'm|i am|call me)\s+([a-zA-Z]+)/i);
                    if (nameMatch) {
                        memoryContent = `User's name: ${nameMatch[1]}\n\n${memoryContent}`;
                    }
                    
                    // Extract personal facts (I have, I own, I gave, I'm going, etc.)
                    const factPatterns = [
                        /(?:i have|i own|i like|i prefer|i want)\s+(.+)/i,
                        /(?:i've given|i gave|i'm giving|i'm going to give)\s+(?:@?\w+)?\s*(\d+)\s*(?:gold|coins?|pieces?)/i,
                        /(?:i'm going|i'm leaving)\s+(?:to|with)\s+(.+)/i
                    ];
                    
                    for (const pattern of factPatterns) {
                        const factMatch = question.match(pattern);
                        if (factMatch) {
                            memoryContent = `User fact: ${factMatch[1] || factMatch[0]}\n\n${memoryContent}`;
                            break;
                        }
                    }
                    
                    // Get user info for storing username/display name
                    const user = message.author;
                    const username = user.username;
                    const displayName = user.displayName || user.globalName || user.username;
                    
                    // Extract mentioned user ID if any (for facts about other users like "I gave @alexei 20 gold pieces")
                    const mentionedUserMatch = question.match(/<@!?(\d+)>/);
                    const mentionedUserId = mentionedUserMatch ? mentionedUserMatch[1] : null;
                    
                    const result = await memoryService.storeMemory(
                        message.channel.id,  // channel_id instead of userId
                        memoryContent,
                        'conversation',
                        { source: useRAG ? 'rag_response' : 'chat_response' },
                        message.channel.name,  // channel name instead of username/displayName
                        userId,  // user_id for better relevance
                        username,  // username for better relevance
                        mentionedUserId  // mentioned_user_id if someone was mentioned
                    );
                    console.log(`✅ Channel memory stored for channel ${message.channel.id}:`, result);
                } catch (error) {
                    console.error('❌ Error storing user memory:', error);
                    console.error('Error details:', error.message, error.stack);
                }
            })();
        }
        
        // Send response using embeds with pagination
        let answer = response.answer || '';
        const MAX_EMBED_DESCRIPTION = 4096; // Discord embed description limit
        const PAGINATION_THRESHOLD = 2000; // Use pagination for responses longer than this (better UX)
        
        // Check if this is a YouTube response - detect by checking if URL was YouTube-specific
        // Only check for actual YouTube URLs, not just any tool handler
        const isYouTubeResponse = hasUrl && (
            /youtube\.com|youtu\.be/i.test(question) || 
            (response.source_documents && response.source_documents.some(doc => /youtube\.com|youtu\.be/i.test(String(doc))))
        );
        
        // Check if this is a website response (any URL that's not YouTube)
        const isWebsiteResponse = hasUrl && !isYouTubeResponse;
        
        // Use pagination if response is long OR if it's a YouTube/website URL response
        if (answer.length > PAGINATION_THRESHOLD || ((isYouTubeResponse || isWebsiteResponse) && answer.length > 500)) {
            // Split into pages for embed pagination
            const pages = [];
            let remaining = answer;
            
            while (remaining.length > 0) {
                if (remaining.length <= MAX_EMBED_DESCRIPTION) {
                    pages.push(remaining);
                    break;
                }
                
                // Try to split at a sentence boundary
                let splitPoint = MAX_EMBED_DESCRIPTION;
                const lastPeriod = remaining.lastIndexOf('.', MAX_EMBED_DESCRIPTION);
                const lastNewline = remaining.lastIndexOf('\n', MAX_EMBED_DESCRIPTION);
                
                if (lastPeriod > MAX_EMBED_DESCRIPTION * 0.8) {
                    splitPoint = lastPeriod + 1;
                } else if (lastNewline > MAX_EMBED_DESCRIPTION * 0.8) {
                    splitPoint = lastNewline + 1;
                }
                
                pages.push(remaining.substring(0, splitPoint).trim());
                remaining = remaining.substring(splitPoint).trim();
            }
            
            // Create embed with pagination
            let currentPage = 0;
            const createEmbed = (pageIndex) => {
                const embed = new EmbedBuilder()
                    .setColor(isYouTubeResponse ? 0xFF0000 : 0x5865F2) // Red for YouTube, blurple for others
                    .setDescription(pages[pageIndex])
                    .setFooter({ 
                        text: `Page ${pageIndex + 1} of ${pages.length}`,
                        iconURL: client.user.displayAvatarURL()
                    })
                    .setTimestamp();
                
                // Add title for URL responses
                if (pageIndex === 0) {
                    if (isYouTubeResponse) {
                        embed.setTitle('📺 YouTube Video Summary');
                    } else if (isWebsiteResponse) {
                        embed.setTitle('🌐 Website Summary');
                    }
                }
                
                // Add source information as fields (only on first page)
                if (pageIndex === 0) {
                    // Add document sources
                    if (response.source_documents && response.source_documents.length > 0) {
                        const docList = response.source_documents.slice(0, 5).join(', ');
                        const moreDocs = response.source_documents.length > 5 ? ` (+${response.source_documents.length - 5} more)` : '';
                        embed.addFields({
                            name: '📄 Sources',
                            value: docList + moreDocs || 'None',
                            inline: false
                        });
                    }
                    
                    // Add memory sources
                    if (response.source_memories && response.source_memories.length > 0) {
                        const memoryTypes = response.source_memories.map(m => m.type).filter((v, i, a) => a.indexOf(v) === i);
                        embed.addFields({
                            name: '🧠 Memories Used',
                            value: `${response.memories_used || 0} memories (${memoryTypes.join(', ')})`,
                            inline: true
                        });
                    }
                    
                    // Add chunk count
                    embed.addFields({
                        name: '📊 Context',
                        value: `${response.context_chunks || 0} chunks retrieved`,
                        inline: true
                    });
                }
                
                return embed;
            };
            
            const createButtons = (pageIndex) => {
                const row = new ActionRowBuilder();
                
                if (pageIndex > 0) {
                    row.addComponents(
                        new ButtonBuilder()
                            .setCustomId(`page_prev_${message.id}`)
                            .setLabel('◀ Previous')
                            .setStyle(ButtonStyle.Primary)
                    );
                }
                
                if (pageIndex < pages.length - 1) {
                    row.addComponents(
                        new ButtonBuilder()
                            .setCustomId(`page_next_${message.id}`)
                            .setLabel('Next ▶')
                            .setStyle(ButtonStyle.Primary)
                    );
                }
                
                return row.components.length > 0 ? row : null;
            };
            
            // Send first page
            const replyOptions = {
                embeds: [createEmbed(0)],
                allowedMentions: { repliedUser: false }
            };
            
            const buttons = createButtons(0);
            if (buttons) {
                replyOptions.components = [buttons];
            }
            
            const sentMessage = await message.reply(replyOptions);
            
            // Store pagination state (in memory - could be improved with a Map)
            if (!client.paginationState) {
                client.paginationState = new Map();
            }
            client.paginationState.set(`page_${message.id}`, {
                pages: pages,
                currentPage: 0,
                messageId: sentMessage.id,
                userId: userId,
                sourceInfo: {
                    documents: response.source_documents || [],
                    memories: response.source_memories || [],
                    memoryCount: response.memories_used || 0,
                    chunkCount: response.context_chunks || 0
                }
            });
            
            // Set up button collector
            const collector = sentMessage.createMessageComponentCollector({
                filter: (interaction) => {
                    const state = client.paginationState.get(`page_${message.id}`);
                    return state && interaction.user.id === state.userId;
                },
                time: 300000 // 5 minutes
            });
            
            collector.on('collect', async (interaction) => {
                const state = client.paginationState.get(`page_${message.id}`);
                if (!state) {
                    await interaction.reply({ content: 'This pagination has expired.', ephemeral: true });
                    return;
                }
                
                if (interaction.customId === `page_prev_${message.id}`) {
                    state.currentPage = Math.max(0, state.currentPage - 1);
                } else if (interaction.customId === `page_next_${message.id}`) {
                    state.currentPage = Math.min(state.pages.length - 1, state.currentPage + 1);
                }
                
                const updateOptions = {
                    embeds: [createEmbed(state.currentPage)],
                    components: createButtons(state.currentPage) ? [createButtons(state.currentPage)] : []
                };
                
                await interaction.update(updateOptions);
            });
            
            collector.on('end', () => {
                client.paginationState.delete(`page_${message.id}`);
            });
            
        } else {
            // Single page embed
            const embed = new EmbedBuilder()
                .setColor(isYouTubeResponse ? 0xFF0000 : 0x5865F2) // Red for YouTube, blurple for others
                .setDescription(answer)
                .setFooter({ 
                    text: 'Response',
                    iconURL: client.user.displayAvatarURL()
                })
                .setTimestamp();
            
            // Add title for URL responses
            if (isYouTubeResponse) {
                embed.setTitle('📺 YouTube Video Summary');
            } else if (isWebsiteResponse) {
                embed.setTitle('🌐 Website Summary');
            }
            
            // Add source information as fields
            if (response.source_documents && response.source_documents.length > 0) {
                const docList = response.source_documents.slice(0, 5).join(', ');
                const moreDocs = response.source_documents.length > 5 ? ` (+${response.source_documents.length - 5} more)` : '';
                embed.addFields({
                    name: '📄 Sources',
                    value: docList + moreDocs || 'None',
                    inline: false
                });
            }
            
            if (response.source_memories && response.source_memories.length > 0) {
                const memoryTypes = response.source_memories.map(m => m.type).filter((v, i, a) => a.indexOf(v) === i);
                embed.addFields({
                    name: '🧠 Memories Used',
                    value: `${response.memories_used || 0} memories (${memoryTypes.join(', ')})`,
                    inline: true
                });
            }
            
            embed.addFields({
                name: '📊 Context',
                value: `${response.context_chunks || 0} chunks retrieved`,
                inline: true
            });
            
            await message.reply({
                embeds: [embed],
                allowedMentions: { repliedUser: false }
            });
        }
        
    } catch (error) {
        console.error('Error processing question:', error);
        await message.reply({
            content: 'Sorry, I encountered an error processing your question. Please try again.',
            allowedMentions: { repliedUser: false }
        });
    }
}

// Interaction handler (slash commands and buttons)
client.on(Events.InteractionCreate, async interaction => {
    // Handle button interactions (pagination)
    if (interaction.isButton()) {
        const customId = interaction.customId;
        
        // Check if it's a pagination button
        if (customId.startsWith('page_prev_') || customId.startsWith('page_next_')) {
            // Extract message ID from custom ID (format: page_prev_123456789 or page_next_123456789)
            const parts = customId.split('_');
            const messageId = parts.slice(2).join('_'); // Get everything after page_prev_ or page_next_
            const state = client.paginationState?.get(`page_${messageId}`);
            
            if (!state) {
                await interaction.reply({ 
                    content: 'This pagination has expired. Please ask your question again.', 
                    ephemeral: true 
                });
                return;
            }
            
            // Verify user owns this pagination
            if (interaction.user.id !== state.userId) {
                await interaction.reply({ 
                    content: 'Only the person who asked the question can navigate pages.', 
                    ephemeral: true 
                });
                return;
            }
            
            // Update page
            if (customId.startsWith('page_prev_')) {
                state.currentPage = Math.max(0, state.currentPage - 1);
            } else if (customId.startsWith('page_next_')) {
                state.currentPage = Math.min(state.pages.length - 1, state.currentPage + 1);
            }
            
            // Create updated embed and buttons
            const createEmbed = (pageIndex) => {
                const embed = new EmbedBuilder()
                    .setColor(0x5865F2)
                    .setDescription(state.pages[pageIndex])
                    .setFooter({ 
                        text: `Page ${pageIndex + 1} of ${state.pages.length}`,
                        iconURL: client.user.displayAvatarURL()
                    })
                    .setTimestamp();
                
                // Add source information only on first page
                if (pageIndex === 0 && state.sourceInfo) {
                    if (state.sourceInfo.documents && state.sourceInfo.documents.length > 0) {
                        const docList = state.sourceInfo.documents.slice(0, 5).join(', ');
                        const moreDocs = state.sourceInfo.documents.length > 5 ? ` (+${state.sourceInfo.documents.length - 5} more)` : '';
                        embed.addFields({
                            name: '📄 Sources',
                            value: docList + moreDocs || 'None',
                            inline: false
                        });
                    }
                    
                    if (state.sourceInfo.memories && state.sourceInfo.memories.length > 0) {
                        const memoryTypes = state.sourceInfo.memories.map(m => m.type).filter((v, i, a) => a.indexOf(v) === i);
                        embed.addFields({
                            name: '🧠 Memories Used',
                            value: `${state.sourceInfo.memoryCount || 0} memories (${memoryTypes.join(', ')})`,
                            inline: true
                        });
                    }
                    
                    embed.addFields({
                        name: '📊 Context',
                        value: `${state.sourceInfo.chunkCount || 0} chunks retrieved`,
                        inline: true
                    });
                }
                
                return embed;
            };
            
            const createButtons = (pageIndex) => {
                const row = new ActionRowBuilder();
                
                if (pageIndex > 0) {
                    row.addComponents(
                        new ButtonBuilder()
                            .setCustomId(`page_prev_${messageId}`)
                            .setLabel('◀ Previous')
                            .setStyle(ButtonStyle.Primary)
                    );
                }
                
                if (pageIndex < state.pages.length - 1) {
                    row.addComponents(
                        new ButtonBuilder()
                            .setCustomId(`page_next_${messageId}`)
                            .setLabel('Next ▶')
                            .setStyle(ButtonStyle.Primary)
                    );
                }
                
                return row.components.length > 0 ? row : null;
            };
            
            const updateOptions = {
                embeds: [createEmbed(state.currentPage)],
                components: createButtons(state.currentPage) ? [createButtons(state.currentPage)] : []
            };
            
            await interaction.update(updateOptions);
            return;
        }
    }
    
    // Handle slash commands
    if (!interaction.isChatInputCommand()) return;
    
    const command = client.commands.get(interaction.commandName);
    
    if (!command) {
        console.error(`No command matching ${interaction.commandName} was found.`);
        return;
    }
    
    try {
        await command.execute(interaction, conversationManager, ragService, memoryService, documentService, configManager);
    } catch (error) {
        console.error(`Error executing ${interaction.commandName}:`, error);
        const errorMessage = { content: 'There was an error while executing this command!', ephemeral: true };
        if (interaction.replied || interaction.deferred) {
            await interaction.followUp(errorMessage);
        } else {
            await interaction.reply(errorMessage);
        }
    }
});

// Error handlers to prevent crashes
process.on('unhandledRejection', (error) => {
    console.error('❌ Unhandled promise rejection:', error);
    // Don't exit - keep the bot running
});

process.on('uncaughtException', (error) => {
    console.error('❌ Uncaught exception:', error);
    // Don't exit - keep the bot running
});

// Handle disconnects and reconnections
client.on(Events.Error, (error) => {
    console.error('❌ Discord client error:', error);
});

client.on(Events.ShardDisconnect, (event, id) => {
    console.log(`⚠️  Shard ${id} disconnected:`, event);
    console.log('🔄 Will attempt to reconnect automatically...');
});

client.on(Events.ShardReconnecting, (id) => {
    console.log(`🔄 Shard ${id} reconnecting...`);
});

client.on(Events.ShardReady, (id) => {
    console.log(`✅ Shard ${id} is ready!`);
});

// Handle disconnects - Discord.js should auto-reconnect, but we'll log it
client.on(Events.Disconnect, () => {
    console.log('⚠️  Bot disconnected from Discord');
    console.log('🔄 Discord.js will attempt to reconnect automatically...');
});

client.on(Events.Ready, () => {
    console.log('✅ Bot reconnected and ready!');
});

// Login
const token = process.env.DISCORD_TOKEN;
if (!token) {
    console.error('❌ DISCORD_TOKEN not found in environment variables!');
    process.exit(1);
}

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down gracefully...');
    ragService.shutdown();
    client.destroy();
    process.exit(0);
});

process.on('SIGTERM', () => {
    console.log('\n🛑 Shutting down gracefully...');
    ragService.shutdown();
    client.destroy();
    process.exit(0);
});

client.login(token).catch((error) => {
    console.error('❌ Error logging in:', error);
    ragService.shutdown();
    process.exit(1);
});

