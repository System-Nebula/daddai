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
                .setDescription('PDF, DOCX, TXT, LOG, MD, CSV, JSON, or IPYNB (Jupyter) file to upload')
                .setRequired(true)),
    
    async execute(interaction, conversationManager, ragService, memoryService, documentService, configManager) {
        await interaction.deferReply();
        
        const attachment = interaction.options.getAttachment('file');
        const userId = interaction.user.id;
        
        // Check file type
        const allowedExtensions = ['.pdf', '.docx', '.doc', '.txt', '.md', '.log', '.csv', '.json', '.ipynb'];
        const fileExtension = path.extname(attachment.name).toLowerCase();
        
        if (!allowedExtensions.includes(fileExtension)) {
            await interaction.editReply({
                content: `❌ Unsupported file type. Supported: ${allowedExtensions.join(', ')}`
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

