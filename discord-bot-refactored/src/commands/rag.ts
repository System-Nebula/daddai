import { SlashCommandBuilder, type ChatInputCommandInteraction } from 'discord.js';
import type ConversationManager from '../conversationManager.js';
import type PersistentRAGService from '../ragServicePersistent.js';
import type { default as MemoryService } from '../memoryService.js';
import type DocumentService from '../documentService.js';
import type ConfigManager from '../configManager.js';

export default {
    data: new SlashCommandBuilder()
        .setName('rag')
        .setDescription('Query the RAG system with a question')
        .addStringOption(option =>
            option.setName('question')
                .setDescription('Your question about the documents')
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
        
        const question = interaction.options.getString('question');
        if (!question) {
            await interaction.editReply('Please provide a question.');
            return;
        }
        
        const userId = interaction.user.id;
        const channelId = interaction.channel.id;
        
        try {
            // Get conversation history
            const conversationHistory = await conversationManager.getRecentConversation(userId, 3);
            
            // Convert to expected format
            const formattedHistory = conversationHistory.map(msg => ({
                role: msg.role || 'user',
                content: msg.content || ''
            }));
            
            // Query RAG system with channel_id for enhanced features
            const response = await ragService.queryWithContext(
                question,
                formattedHistory,
                userId,
                channelId
            ) as { answer?: string };
            
            // Save conversation
            if (response.answer) {
                await conversationManager.addMessage(userId, question, response.answer, channelId);
            }
            
            // Send response
            await interaction.editReply({
                content: response.answer || 'No response generated.',
                allowedMentions: { repliedUser: false }
            });
            
        } catch (error) {
            const err = error as Error;
            console.error('Error in /rag command:', error);
            await interaction.editReply('Sorry, I encountered an error processing your question.');
        }
    },
};

