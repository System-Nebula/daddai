const { SlashCommandBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('rag')
        .setDescription('Query the RAG system with a question')
        .addStringOption(option =>
            option.setName('question')
                .setDescription('Your question about the documents')
                .setRequired(true)),
    
    async execute(interaction, conversationManager, ragService, memoryService, documentService, configManager) {
        await interaction.deferReply();
        
        const question = interaction.options.getString('question');
        const userId = interaction.user.id;
        const channelId = interaction.channel.id;
        
        try {
            // Get conversation history
            const conversationHistory = await conversationManager.getRecentConversation(userId, 3);
            
            // Query RAG system with channel_id for enhanced features
            const response = await ragService.queryWithContext(
                question,
                conversationHistory,
                userId,
                channelId  // Pass channel_id for enhanced memory and user relations
            );
            
            // Save conversation
            await conversationManager.addMessage(userId, question, response.answer, channelId);
            
            // Send response
            await interaction.editReply({
                content: response.answer,
                allowedMentions: { repliedUser: false }
            });
            
        } catch (error) {
            console.error('Error in /rag command:', error);
            await interaction.editReply('Sorry, I encountered an error processing your question.');
        }
    },
};

