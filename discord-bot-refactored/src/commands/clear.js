const { SlashCommandBuilder } = require('discord.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('clear')
        .setDescription('Clear your conversation history'),
    
    async execute(interaction, conversationManager, ragService, memoryService, documentService, configManager) {
        const userId = interaction.user.id;
        
        try {
            await conversationManager.clearConversation(userId);
            await interaction.reply({
                content: '✅ Your conversation history has been cleared!',
                ephemeral: true
            });
        } catch (error) {
            console.error('Error clearing conversation:', error);
            await interaction.reply({
                content: '❌ Error clearing conversation history.',
                ephemeral: true
            });
        }
    },
};

