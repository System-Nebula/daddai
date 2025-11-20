import { SlashCommandBuilder, AttachmentBuilder, type ChatInputCommandInteraction } from 'discord.js';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import * as https from 'https';
import * as http from 'http';

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
import type ConversationManager from '../conversationManager.js';
import type PersistentRAGService from '../ragServicePersistent.js';
import type { default as MemoryService } from '../memoryService.js';
import type DocumentService from '../documentService.js';
import type ConfigManager from '../configManager.js';

export default {
    data: new SlashCommandBuilder()
        .setName('upload')
        .setDescription('Upload a document to the shared knowledge base')
        .addAttachmentOption(option =>
            option.setName('file')
                .setDescription('Document or text file to upload (PDF, DOCX, PPTX, HTML, Markdown, code files, etc.)')
                .setRequired(true)),
    
    async execute(
        interaction: ChatInputCommandInteraction,
        conversationManager: ConversationManager,
        ragService: PersistentRAGService,
        memoryService: typeof MemoryService,
        documentService: DocumentService,
        configManager: ConfigManager
    ) {
        await interaction.deferReply();
        
        const attachment = interaction.options.getAttachment('file');
        if (!attachment) {
            await interaction.editReply({
                content: '❌ No file attached.'
            });
            return;
        }
        
        const userId = interaction.user.id;
        
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
        const fileExtension = path.extname(attachment.name).toLowerCase();
        
        if (!allowedExtensions.includes(fileExtension)) {
            await interaction.editReply({
                content: `❌ Unsupported file type. Supported formats include: PDF, DOCX, PPTX, HTML, Markdown, text files, code files, and more.`
            });
            return;
        }
        
        // Check file size (limit to 25MB for Discord)
        if (attachment.size > 25 * 1024 * 1024) {
            await interaction.editReply({
                content: '❌ File too large. Maximum size is 25MB.'
            });
            return;
        }
        
        try {
            // Download file from Discord
            const buffer = await new Promise<Buffer>((resolve, reject) => {
                const url = new URL(attachment.url);
                const client = url.protocol === 'https:' ? https : http;
                
                client.get(attachment.url, (res) => {
                    const chunks: Buffer[] = [];
                    res.on('data', (chunk: Buffer) => chunks.push(chunk));
                    res.on('end', () => resolve(Buffer.concat(chunks)));
                    res.on('error', reject);
                }).on('error', reject);
            });
            
            // Save to temp directory
            const tempDir = path.join(__dirname, '..', '..', '..', 'temp');
            if (!fs.existsSync(tempDir)) {
                fs.mkdirSync(tempDir, { recursive: true });
            }
            
            const tempFilePath = path.join(tempDir, `${Date.now()}_${attachment.name}`);
            fs.writeFileSync(tempFilePath, buffer);
            
            // Upload document
            const result = await documentService.uploadDocument(
                userId,
                tempFilePath,
                attachment.name
            ) as { chunks?: number; success?: boolean };
            
            // Clean up temp file
            try {
                fs.unlinkSync(tempFilePath);
            } catch (error) {
                console.error('Error deleting temp file:', error);
            }
            
            await interaction.editReply({
                content: `✅ Document uploaded and processed!\n**File:** ${attachment.name}\n**Chunks:** ${result.chunks || 0}\n\nThis document is now available to all users.`,
                files: result.chunks && result.chunks > 0 ? [] : undefined
            });
        } catch (error) {
            const err = error as Error;
            console.error('Error uploading document:', error);
            await interaction.editReply({
                content: `❌ Error processing document: ${err.message}`
            });
        }
    },
};

