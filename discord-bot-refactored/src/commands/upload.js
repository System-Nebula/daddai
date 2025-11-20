const { SlashCommandBuilder, AttachmentBuilder } = require('discord.js');
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('upload')
        .setDescription('Upload a document to the shared knowledge base')
                .addAttachmentOption(option =>
            option.setName('file')
                .setDescription('Document or text file to upload (PDF, DOCX, PPTX, HTML, Markdown, code files, etc.)')
                .setRequired(true)),
    
    async execute(interaction, conversationManager, ragService, memoryService, documentService, configManager) {
        await interaction.deferReply();
        
        const attachment = interaction.options.getAttachment('file');
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
            // Download file using Node.js http/https
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
            const tempDir = path.join(__dirname, '..', '..', 'temp');
            if (!fs.existsSync(tempDir)) {
                fs.mkdirSync(tempDir, { recursive: true });
            }
            
            const tempFilePath = path.join(tempDir, `${Date.now()}_${attachment.name}`);
            fs.writeFileSync(tempFilePath, buffer);
            
            // Upload and process
            await interaction.editReply({
                content: '⏳ Processing document... This may take a minute.'
            });
            
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
            
            await interaction.editReply({
                content: `✅ Document uploaded successfully!\n**File:** ${attachment.name}\n**Chunks:** ${result.chunks}\n\nThis document is now available to all users.`
            });
            
        } catch (error) {
            console.error('Error uploading document:', error);
            await interaction.editReply({
                content: `❌ Error processing document: ${error.message}`
            });
        }
    },
};

