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
const conversationManager = new ConversationManager();
const ragService = new PersistentRAGService(); // Use persistent RAG service
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
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js') && file !== 'deploy.js');

// Load commands for execution
for (const file of commandFiles) {
    const filePath = path.join(commandsPath, file);
    const command = require(filePath);
    if ('data' in command && 'execute' in command) {
        // Handle subcommands
        if (command.data.name) {
            client.commands.set(command.data.name, command);
        }
    }
}

// Prepare commands for registration
const commands = [];
for (const file of commandFiles) {
    const filePath = path.join(commandsPath, file);
    const command = require(filePath);
    if ('data' in command) {
        commands.push(command.data.toJSON());
    }
}

// REST client for command management
const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);

// Function to clear and register commands for a guild
async function refreshCommandsForGuild(guildId) {
    try {
        // Get CLIENT_ID from application info
        const application = await rest.get(Routes.oauth2CurrentApplication());
        const CLIENT_ID = application.id;
        
        console.log(`🔄 Clearing existing commands for guild ${guildId}...`);
        
        // Clear all existing commands
        try {
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
            console.log(`⚠️  Error clearing commands: ${error.message}`);
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
        
        const data = await rest.put(
            Routes.applicationGuildCommands(CLIENT_ID, guildId),
            { body: commands }
        );
        
        console.log(`✅ Successfully registered ${data.length} commands for guild ${guildId}`);
        console.log('\n📋 Registered commands:');
        data.forEach((cmd, index) => {
            console.log(`   ${index + 1}. /${cmd.name} - ${cmd.description || 'No description'}`);
        });
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
        
        // Clear and register commands for all guilds the bot is in
        // Run this asynchronously so it doesn't block the bot from starting
        (async () => {
            try {
                logger.info(`🔄 Refreshing commands for all guilds...`);
                const guilds = Array.from(client.guilds.cache.values());
                
                for (const guild of guilds) {
                    await refreshCommandsForGuild(guild.id);
                    // Small delay between guilds to avoid rate limits
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
                logger.info(`✅ Command refresh complete!`);
            } catch (error) {
                logger.error('❌ Error during command refresh:', { error: error.message, stack: error.stack });
                // Don't crash the bot if command registration fails
            }
        })();
    } else {
        logger.info('🔄 Bot reconnected - skipping command refresh');
    }
});

// Handle bot joining a new guild
client.on(Events.GuildCreate, async (guild) => {
    logger.info(`🆕 Bot joined new guild: ${guild.name} (${guild.id})`);
    try {
        await refreshCommandsForGuild(guild.id);
    } catch (error) {
        logger.error(`❌ Error refreshing commands for new guild ${guild.id}:`, { error: error.message, stack: error.stack });
        // Don't crash - bot should stay online
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
        // Auto-detect: Check if message has attachments (document upload)
        if (message.attachments.size > 0) {
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
        
        // Auto-detect: Check if message is a question (contains question mark or mentions bot)
        const isMentioned = message.mentions.has(client.user);
        const hasQuestionMark = message.content.includes('?');
        const isQuestion = message.content.trim().length > 10; // Reasonable length for a question
        
        if (isMentioned || (hasQuestionMark && isQuestion)) {
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
            await handleQuestion(message);
            return;
        }
        
        // Ignore short messages that aren't questions
        if (message.content.trim().length < 10) return;
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
    
    // Check file type
    const allowedExtensions = ['.pdf', '.docx', '.doc', '.txt', '.md', '.log', '.csv', '.json', '.ipynb'];
    const path = require('path');
    const fileExtension = path.extname(attachment.name).toLowerCase();
    
    if (!allowedExtensions.includes(fileExtension)) {
        await message.react('❌');
        await message.reply({
            content: `❌ Unsupported file type. Supported: ${allowedExtensions.join(', ')}`,
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
    
    // EXCLUDE: User fact questions that should use memory, not RAG
    const userFactPatterns = [
        /(?:how many|how much|what do i have|what's in my|my inventory|my coins|my gold|i have|i own|i gave|i gave|i'm going|i'm leaving)/i,
        /(?:inventory|coins?|gold|pieces?|apples?|items?|things?)\s+(?:do i have|in my|i have|i own)/i,
        /(?:i've given|i gave|i'm giving|i'm going to give)/i,
        /(?:how many|how much)\s+(?:do i|does|have i|do you know)/i
    ];
    
    for (const pattern of userFactPatterns) {
        if (pattern.test(question)) {
            return false; // Use memory, not RAG
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
        /^(lol|haha|hehe|rofl|lmao|nice|cool|awesome|great)[\s!.,]*$/i
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

async function handleQuestion(message) {
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
        
        // Check for special "list all documents" or "summarize all documents" queries
        const lowerQuestion = cleanedQuestion.toLowerCase();
        const isListAllDocsQuery = /(?:list|show|summarize|what|which).*(?:all|each|every).*(?:document|file|doc)/i.test(cleanedQuestion) ||
                                   /(?:document|file|doc).*(?:available|have|you have|stored)/i.test(cleanedQuestion);
        
        // Detect if user is asking about a specific document
        let targetDocId = null;
        let targetDocFilename = null;
        let isSummarizeSingleDoc = false;
        let isCompareDocs = false;
        let isCompareMultipleDocs = false;
        let compareDoc1Id = null;
        let compareDoc1Filename = null;
        let compareDoc2Id = null;
        let compareDoc2Filename = null;
        let compareDocPattern = null;
        
        // Check for multi-document comparison patterns (e.g., "what changed from our build logs")
        const multiComparePatterns = [
            /(?:what changed|what's different|what are the differences|changes|compare|difference)\s+(?:from|in|across|between|in my|in our|in the)\s+(?:our|the|all|all of|all our|my)?\s*(?:build logs?|build-logs?|documents?|files?|logs?)/i,
            /(?:what changed|what's different|what are the differences|changes|compare|difference)\s+(?:from|in|across|between|in my|in our|in the)\s+(?:our|the|all|all of|all our|my)?\s*([\w\-]+)\s*(?:logs?|documents?|files?)/i,
            /(?:compare|difference|differences|changes)\s+(?:all|all of|all our|our|the|my)\s*(?:build logs?|build-logs?|documents?|files?|logs?)/i,
            /(?:compare|difference|differences|changes)\s+(?:all|all of|all our|our|the|my)\s*([\w\-]+)\s*(?:logs?|documents?|files?)/i,
            /(?:what are|what's|what)\s+(?:the\s+)?(?:differences?|changes?|different)\s+(?:in|from|between|across)\s+(?:my|our|the|all)?\s*(?:build logs?|build-logs?|documents?|files?|logs?)/i,
            /(?:what are|what's|what)\s+(?:the\s+)?(?:differences?|changes?|different)\s+(?:in|from|between|across)\s+(?:my|our|the|all)?\s*([\w\-]+)\s*(?:logs?|documents?|files?)/i
        ];
        
        for (const pattern of multiComparePatterns) {
            const match = cleanedQuestion.match(pattern);
            if (match) {
                isCompareMultipleDocs = true;
                // Extract pattern if specified (e.g., "build logs" -> "build-logs")
                if (match[1]) {
                    compareDocPattern = match[1].toLowerCase().replace(/\s+/g, '-');
                }
                break;
            }
        }
        
        // Check for two-document comparison patterns (only if not multi-doc comparison)
        if (!isCompareMultipleDocs) {
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
        }
        
        // Check for "summarize [filename]" pattern specifically
        if (!isCompareDocs && !isCompareMultipleDocs) {
            const summarizePattern = /^summarize\s+([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))$/i;
            const summarizeMatch = cleanedQuestion.match(summarizePattern);
            if (summarizeMatch && summarizeMatch[1]) {
                targetDocFilename = summarizeMatch[1];
                isSummarizeSingleDoc = true;
            } else {
                // Try to extract document filename from cleaned question (without mentions)
                // Patterns: "in document X", "from X.pdf", "what does X say", "according to X"
                const docFilenamePatterns = [
                    /(?:in|from|about|according to|based on|in the document|in the file)\s+([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))/i,
                    /(?:document|file|paper)\s+([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))/i,
                    /"([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))"/i,
                    /'([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))'/i,
                    /\b([\w\-\.]+\.(?:pdf|docx?|txt|md|log|csv))\b/i  // Any filename pattern
                ];
                
                for (const pattern of docFilenamePatterns) {
                    const match = cleanedQuestion.match(pattern);
                    if (match && match[1]) {
                        targetDocFilename = match[1];
                        break;
                    }
                }
            }
        }
        
        // If comparing multiple documents, find all matching documents
        if (isCompareMultipleDocs) {
            try {
                const allDocs = await documentService.getAllDocuments();
                const documents = allDocs.documents || allDocs || [];
                
                // Filter documents by pattern if specified
                let matchingDocs = documents;
                if (compareDocPattern) {
                    matchingDocs = documents.filter(doc => 
                        doc.file_name.toLowerCase().includes(compareDocPattern)
                    );
                }
                
                // Sort by upload date (oldest first)
                matchingDocs.sort((a, b) => {
                    const dateA = new Date(a.uploaded_at || 0);
                    const dateB = new Date(b.uploaded_at || 0);
                    return dateA - dateB;
                });
                
                console.log(`🎯 Found ${matchingDocs.length} documents to compare (sorted by date)`);
                
                if (matchingDocs.length < 2) {
                    response = {
                        answer: `I found ${matchingDocs.length} document(s) matching your query. I need at least 2 documents to compare.`,
                        context_chunks: 0,
                        memories_used: 0,
                        source_documents: matchingDocs.map(d => d.file_name),
                        source_memories: []
                    };
                } else {
                    // Compare documents sequentially (doc1 vs doc2, doc2 vs doc3, etc.)
                    const comparisons = [];
                    
                    for (let i = 0; i < matchingDocs.length - 1; i++) {
                        const doc1 = matchingDocs[i];
                        const doc2 = matchingDocs[i + 1];
                        
                        try {
                            // Get chunks from both documents
                            const chunks1Response = await documentService.getDocumentChunks(doc1.id);
                            const chunks2Response = await documentService.getDocumentChunks(doc2.id);
                            const chunks1 = chunks1Response.chunks || [];
                            const chunks2 = chunks2Response.chunks || [];
                            
                            if (chunks1.length === 0 || chunks2.length === 0) {
                                comparisons.push(`**${doc1.file_name} → ${doc2.file_name}**: Could not compare (one or both documents have no content)`);
                                continue;
                            }
                            
                            // Get full document text (no truncation - let the comparison service handle compression)
                            const doc1Text = chunks1
                                .map(chunk => chunk.text || '')
                                .join('\n\n');
                            
                            const doc2Text = chunks2
                                .map(chunk => chunk.text || '')
                                .join('\n\n');
                            
                            // Use smart document comparison service for intelligent compression and comparison
                            try {
                                console.log(`🔄 Comparing ${doc1.file_name} (${doc1Text.length} chars) vs ${doc2.file_name} (${doc2Text.length} chars)...`);
                                const comparisonResult = await compareDocuments(
                                    doc1Text,
                                    doc2Text,
                                    doc1.file_name,
                                    doc2.file_name
                                );
                                
                                console.log(`✅ Comparison complete for ${doc1.file_name} → ${doc2.file_name}`);
                                console.log(`   Comparison result keys: ${Object.keys(comparisonResult).join(', ')}`);
                                console.log(`   Comparison length: ${comparisonResult.comparison?.length || 0} chars`);
                                console.log(`   Has error: ${!!comparisonResult.error}`);
                                if (comparisonResult.error) {
                                    console.log(`   Error: ${comparisonResult.error}`);
                                }
                                // Log first 200 chars of comparison to see what we got
                                if (comparisonResult.comparison) {
                                    console.log(`   Comparison preview: ${comparisonResult.comparison.substring(0, 200)}...`);
                                }
                                
                                // Check if comparison result indicates an error
                                let comparison = comparisonResult.comparison || '';
                                if (comparisonResult.error) {
                                    console.warn(`   ⚠️ Comparison had an error: ${comparisonResult.error}`);
                                    // If comparison is just an error message, use it; otherwise append error info
                                    if (comparison.includes('Error comparing')) {
                                        comparison = comparison; // Already has error message
                                    } else {
                                        comparison = `${comparison}\n\n⚠️ Note: Comparison encountered an issue: ${comparisonResult.error}`;
                                    }
                                }
                                
                                if (!comparison || comparison.length < 50) {
                                    console.warn(`   ⚠️ Comparison result seems too short or empty (${comparison.length} chars), using fallback`);
                                    comparison = comparisonResult.error 
                                        ? `Error during comparison: ${comparisonResult.error}` 
                                        : 'Could not generate detailed comparison. The documents may be too large or similar.';
                                }
                                const compressionInfo = comparisonResult.doc1_original_length && comparisonResult.doc2_original_length
                                    ? `\n\n*[Compressed: ${Math.round(comparisonResult.compression_ratio_doc1 * 100)}% and ${Math.round(comparisonResult.compression_ratio_doc2 * 100)}% of original size]*`
                                    : '';
                                
                                comparisons.push(`**${doc1.file_name} → ${doc2.file_name}**${compressionInfo}\n${comparison}`);
                                console.log(`   Added comparison to array (total: ${comparisons.length})`);
                            } catch (error) {
                                console.error(`❌ Error in smart comparison: ${error.message}`);
                                console.error(`   Stack: ${error.stack}`);
                                // Fallback to simple comparison
                                const doc1TextShort = doc1Text.substring(0, 3000);
                                const doc2TextShort = doc2Text.substring(0, 3000);
                                const comparisonPrompt = `Compare these two documents and identify what changed. Focus on errors, warnings, metrics, and key differences.

Document 1 (older): ${doc1.file_name}
${doc1TextShort}${doc1Text.length > 3000 ? '\n\n[Content truncated...]' : ''}

Document 2 (newer): ${doc2.file_name}
${doc2TextShort}${doc2Text.length > 3000 ? '\n\n[Content truncated...]' : ''}`;
                                
                                const comparisonResponse = await Promise.race([
                                    chatService.chat(comparisonPrompt, []),
                                    new Promise((_, reject) => 
                                        setTimeout(() => reject(new Error('Comparison timeout')), 20000)
                                    )
                                ]);
                                
                                comparisons.push(`**${doc1.file_name} → ${doc2.file_name}**\n${comparisonResponse || 'Could not generate comparison'}`);
                            }
                            
                        } catch (error) {
                            console.error(`Error comparing ${doc1.file_name} and ${doc2.file_name}:`, error);
                            comparisons.push(`**${doc1.file_name} → ${doc2.file_name}**: Error - ${error.message}`);
                        }
                    }
                    
                    if (comparisons.length > 0) {
                        const comparisonText = comparisons.join('\n\n---\n\n');
                        console.log(`📝 Setting response with ${comparisons.length} comparison(s), total length: ${comparisonText.length} chars`);
                        response = {
                            answer: `**Changes Across ${matchingDocs.length} Documents** (sorted oldest → newest):\n\n${comparisonText}`,
                            context_chunks: matchingDocs.reduce((sum, d) => sum + (d.chunk_count || 0), 0),
                            memories_used: 0,
                            source_documents: matchingDocs.map(d => d.file_name),
                            source_memories: []
                        };
                        console.log(`✅ Response set successfully`);
                    } else {
                        console.log(`⚠️ No comparisons generated (comparisons.length = ${comparisons.length})`);
                        response = {
                            answer: `I couldn't generate comparisons for the ${matchingDocs.length} documents found.`,
                            context_chunks: 0,
                            memories_used: 0,
                            source_documents: matchingDocs.map(d => d.file_name),
                            source_memories: []
                        };
                    }
                }
            } catch (error) {
                console.error('Error comparing multiple documents:', error);
                response = {
                    answer: `I encountered an error while comparing documents: ${error.message}`,
                    context_chunks: 0,
                    memories_used: 0,
                    source_documents: [],
                    source_memories: []
                };
            }
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
        
        // Smart document detection: Try to find documents by name/content keywords OR semantic search
        // This handles cases like "crowd strike 2025 threat report" or "what is the worst country in the report?"
        if (!targetDocId && !targetDocFilename && !isListAllDocsQuery && !isCompareDocs && !isCompareMultipleDocs) {
            try {
                // First, try to extract explicit document name/keywords from question
                // Look for patterns like "in [document name]", "from [document name]", etc.
                const docNamePatterns = [
                    /(?:in|from|about|according to|based on|in the)\s+([a-z0-9\s\-]+?)\s+(?:report|study|analysis|document|paper|guide|manual|handbook)/i,
                    /(?:the|a|an)\s+([a-z0-9\s\-]+?)\s+(?:report|study|analysis|document|paper|guide|manual|handbook)/i,
                    /([a-z0-9\s\-]+?)\s+(?:report|study|analysis|document|paper|guide|manual|handbook)/i
                ];
                
                let detectedDocName = null;
                let foundByName = false;
                
                for (const pattern of docNamePatterns) {
                    const match = cleanedQuestion.match(pattern);
                    if (match && match[1]) {
                        detectedDocName = match[1].trim().toLowerCase();
                        // Extract key terms (remove common words)
                        const keyTerms = detectedDocName
                            .split(/\s+/)
                            .filter(term => term.length > 2 && !['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'man', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use'].includes(term))
                            .slice(0, 5); // Take up to 5 key terms
                        
                        if (keyTerms.length > 0) {
                            console.log(`🔍 Detected potential document name: "${detectedDocName}" (key terms: ${keyTerms.join(', ')})`);
                            
                            // Try to find matching documents by filename
                            const allDocs = await documentService.getAllDocuments();
                            const documents = allDocs.documents || allDocs || [];
                            
                            // Score documents by how many key terms they match
                            const scoredDocs = documents.map(doc => {
                                const fileNameLower = doc.file_name.toLowerCase();
                                let score = 0;
                                for (const term of keyTerms) {
                                    if (fileNameLower.includes(term)) {
                                        score += 1;
                                    }
                                }
                                return { doc, score };
                            }).filter(item => item.score > 0)
                              .sort((a, b) => b.score - a.score);
                            
                            if (scoredDocs.length > 0 && scoredDocs[0].score >= 2) {
                                // Found a document with at least 2 matching terms
                                targetDocId = scoredDocs[0].doc.id;
                                targetDocFilename = scoredDocs[0].doc.file_name;
                                console.log(`✅ Found matching document by name: "${targetDocFilename}" (ID: ${targetDocId}, score: ${scoredDocs[0].score})`);
                                foundByName = true;
                                break;
                            }
                        }
                    }
                }
                
                // If no document found by name, try semantic search for:
                // 1. Generic references like "the report"
                // 2. Document-like terms (logs, files, etc.) that suggest a specific document
                // This handles cases like "what is the worst country in the report?" or "what model was our kohyaa logs trained for?"
                const hasGenericDocReference = (
                    /(?:the|a|an|this|that|your|our)\s+(?:report|study|analysis|document|paper|guide|manual|handbook|file|document|logs?|files?)/i.test(cleanedQuestion) ||
                    /(?:in|from|about|according to|based on)\s+(?:the|a|an|this|that|your|our)\s+(?:report|study|analysis|document|paper|guide|manual|handbook|logs?|files?)/i.test(cleanedQuestion)
                );
                
                // Also check for questions that mention document-like terms (logs, files, etc.) that might refer to a specific document
                const hasDocumentLikeTerms = /(?:our|my|the|a|an|this|that|your)\s+[\w\s\-]+\s+(?:logs?|files?|documents?|reports?|studies?|analyses?)/i.test(cleanedQuestion);
                
                if (!foundByName && (hasGenericDocReference || hasDocumentLikeTerms)) {
                    console.log(`🔍 Detected generic document reference, using semantic search...`);
                    
                    try {
                        // Use semantic search to find the most relevant document(s)
                        const relevantDocsResponse = await documentService.findRelevantDocuments(cleanedQuestion, 3);
                        const relevantDocs = relevantDocsResponse.documents || relevantDocsResponse || [];
                        
                        if (relevantDocs.length > 0 && relevantDocs[0].score >= 0.3) {
                            // Found a relevant document with good semantic match
                            targetDocId = relevantDocs[0].doc_id;
                            targetDocFilename = relevantDocs[0].file_name;
                            console.log(`✅ Found relevant document by semantic search: "${targetDocFilename}" (ID: ${targetDocId}, score: ${relevantDocs[0].score.toFixed(3)})`);
                            
                            // If multiple relevant documents found, log them for transparency
                            if (relevantDocs.length > 1) {
                                console.log(`   Also found ${relevantDocs.length - 1} other relevant document(s):`);
                                for (let i = 1; i < Math.min(relevantDocs.length, 4); i++) {
                                    console.log(`     - ${relevantDocs[i].file_name} (score: ${relevantDocs[i].score.toFixed(3)})`);
                                }
                            }
                        } else {
                            console.log(`⚠️ Semantic search found documents but none met minimum relevance threshold (0.3)`);
                        }
                    } catch (error) {
                        console.error('Error in semantic document search:', error);
                    }
                }
            } catch (error) {
                console.error('Error in smart document detection:', error);
            }
        }
        
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
        if (!response && isSummarizeSingleDoc && targetDocId) {
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
        console.log(`🔍 Response check: response=${response ? 'SET' : 'NOT SET'}, isCompareMultipleDocs=${isCompareMultipleDocs}, isCompareDocs=${isCompareDocs}`);
        // IMPORTANT: Don't overwrite response if it's already set (e.g., from comparison)
        if (!response && needsRAG(cleanedQuestion)) {
            useRAG = true;
            
            // Special handling for "list all documents" queries
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
                        // Summarize each document by getting its chunks directly
                        const summaries = [];
                        for (const doc of documents.slice(0, 10)) { // Limit to 10 docs to avoid timeout
                            try {
                                // Get all chunks for this specific document
                                const chunksResponse = await documentService.getDocumentChunks(doc.id);
                                const chunks = chunksResponse.chunks || [];
                                
                                if (chunks.length === 0) {
                                    summaries.push(`**${doc.file_name}**: No content available`);
                                    continue;
                                }
                                
                                // Combine chunks into document text (limit to first 5000 chars to avoid token limits)
                                const documentText = chunks
                                    .map(chunk => chunk.text || '')
                                    .join('\n\n')
                                    .substring(0, 5000);
                                
                                // Create a summary prompt with the actual document content
                                const summaryPrompt = `Please provide a concise summary of the following document. Focus on the main topics, key points, and purpose of the document.\n\nDocument: ${doc.file_name}\n\nContent:\n${documentText}${chunks.length > 0 && documentText.length >= 5000 ? '\n\n[Content truncated...]' : ''}`;
                                
                                // Use chat service to generate summary (faster than RAG since we already have the content)
                                const summaryResponse = await Promise.race([
                                    chatService.chat(summaryPrompt, []),
                                    new Promise((_, reject) => 
                                        setTimeout(() => reject(new Error('Summary timeout')), 15000)
                                    )
                                ]);
                                
                                const summary = summaryResponse || 'Could not generate summary';
                                summaries.push(`**${doc.file_name}** (${doc.chunk_count || chunks.length} chunks):\n${summary.substring(0, 400)}${summary.length > 400 ? '...' : ''}`);
                            } catch (error) {
                                summaries.push(`**${doc.file_name}**: Could not generate summary (${error.message})`);
                            }
                        }
                        
                        const summaryText = summaries.length > 0 
                            ? summaries.join('\n\n')
                            : 'No summaries could be generated.';
                        
                        response = {
                            answer: `Here are summaries of the ${documents.length} available document(s):\n\n${summaryText}`,
                            context_chunks: documents.reduce((sum, d) => sum + (d.chunk_count || 0), 0),
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
                    response = await Promise.race([
                        ragService.queryWithContext(
                            cleanedQuestion,  // Use cleaned question (without mentions) for RAG
                            conversationHistory, 
                            userId, 
                            message.channel.id,
                            targetDocId,  // doc_id filter
                            targetDocFilename  // doc_filename filter
                        ),
                        new Promise((_, reject) => 
                            setTimeout(() => reject(new Error('RAG timeout')), 30000)  // Reduced from 45s to 30s for faster fallback
                        )
                    ]);
                    
                    // Log what was used in the response
                    if (response) {
                        logger.info(`📊 RAG response: ${response.context_chunks?.length || 0} chunks, ${response.memories?.length || 0} memories`);
                        if ((response.memories?.length || 0) > 0 && (targetDocId || targetDocFilename)) {
                            logger.warn(`⚠️ Warning: Memories were used (${response.memories.length}) even though a specific document was targeted`);
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
        if (!response && !needsRAG(cleanedQuestion) && !targetDocId && !targetDocFilename && !isCasualConversation && !isStatementOrRequest) {
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
                    const memoryPrompt = `You are a helpful assistant with access to conversation history. Answer the user's question based ONLY on the information provided in the conversation history below. Be specific and direct.

Conversation History:
${memoryContext}

User Question: ${cleanedQuestion}

IMPORTANT: 
- Extract specific numbers, facts, and details from the conversation history
- If the question asks about quantities (like "how many gold pieces"), look for exact numbers in the history
- If someone gave something to someone else, state the exact amount
- Be concise and factual

Answer:`;
                    
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
        await conversationManager.addMessage(userId, question, response.answer);
        
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
        
        if (answer.length > MAX_EMBED_DESCRIPTION) {
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
                    .setColor(0x5865F2) // Discord blurple
                    .setDescription(pages[pageIndex])
                    .setFooter({ 
                        text: `Page ${pageIndex + 1} of ${pages.length}`,
                        iconURL: client.user.displayAvatarURL()
                    })
                    .setTimestamp();
                
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
                .setColor(0x5865F2)
                .setDescription(answer)
                .setFooter({ 
                    text: 'Response',
                    iconURL: client.user.displayAvatarURL()
                })
                .setTimestamp();
            
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

