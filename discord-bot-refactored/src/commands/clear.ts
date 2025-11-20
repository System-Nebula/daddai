import { SlashCommandBuilder, type ChatInputCommandInteraction } from 'discord.js';
import type ConversationManager from '../conversationManager.js';
import type PersistentRAGService from '../ragServicePersistent.js';
import type { default as MemoryService } from '../memoryService.js';
import type DocumentService from '../documentService.js';
import type ConfigManager from '../configManager.js';

export default {
    data: new SlashCommandBuilder()
        .setName('clear')
        .setDescription('Clear your conversation history'),
    
    async execute(
        interaction: ChatInputCommandInteraction,
        conversationManager: ConversationManager,
        ragService: PersistentRAGService,
        memoryService: typeof MemoryService,
        documentService: DocumentService,
        configManager: ConfigManager
    ) {
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

