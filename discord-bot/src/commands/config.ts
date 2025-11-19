import { SlashCommandBuilder, EmbedBuilder, ChannelType, type ChatInputCommandInteraction } from 'discord.js';
import type ConversationManager from '../conversationManager.js';
import type PersistentRAGService from '../ragServicePersistent.js';
import type { default as MemoryService } from '../memoryService.js';
import type DocumentService from '../documentService.js';
import type ConfigManager from '../configManager.js';

export default {
    data: new SlashCommandBuilder()
        .setName('config')
        .setDescription('Configure bot settings (Admin only)')
        .addSubcommand(subcommand =>
            subcommand
                .setName('channel')
                .setDescription('Set the channel where the bot responds')
                .addChannelOption(option =>
                    option.setName('channel')
                        .setDescription('Channel for bot responses (leave empty to allow all)')
                        .setRequired(false)))
        .addSubcommand(subcommand =>
            subcommand
                .setName('status')
                .setDescription('View current bot configuration'))
        .addSubcommand(subcommand =>
            subcommand
                .setName('enable')
                .setDescription('Enable bot responses'))
        .addSubcommand(subcommand =>
            subcommand
                .setName('disable')
                .setDescription('Disable bot responses')),
    
    async execute(
        interaction: ChatInputCommandInteraction,
        conversationManager: ConversationManager,
        ragService: PersistentRAGService,
        memoryService: typeof MemoryService,
        documentService: DocumentService,
        configManager: ConfigManager
    ) {
        // Check if user has admin role
        if (!interaction.member || !interaction.member.permissions.has('Administrator')) {
            await interaction.reply({
                content: '❌ You need administrator permissions to use this command.',
                ephemeral: true
            });
            return;
        }
        
        const subcommand = interaction.options.getSubcommand();
        
        try {
            if (subcommand === 'channel') {
                const channel = interaction.options.getChannel('channel');
                
                if (channel) {
                    // Set specific channel
                    if (channel.type !== ChannelType.GuildText) {
                        await interaction.reply({
                            content: '❌ Please select a text channel.',
                            ephemeral: true
                        });
                        return;
                    }
                    
                    configManager.setBotChannel(channel.id);
                    await interaction.reply({
                        content: `✅ Bot will now only respond in <#${channel.id}>`,
                        ephemeral: true
                    });
                } else {
                    // Clear channel restriction (allow all channels)
                    configManager.setBotChannel(null);
                    await interaction.reply({
                        content: '✅ Bot will now respond in all channels',
                        ephemeral: true
                    });
                }
                
            } else if (subcommand === 'status') {
                const channelId = configManager.getBotChannel();
                const enabled = configManager.isResponseEnabled();
                
                const embed = new EmbedBuilder()
                    .setTitle('🤖 Bot Configuration')
                    .setColor(0x5865F2)
                    .addFields(
                        {
                            name: 'Response Channel',
                            value: channelId ? `<#${channelId}>` : 'All channels',
                            inline: true
                        },
                        {
                            name: 'Status',
                            value: enabled ? '✅ Enabled' : '❌ Disabled',
                            inline: true
                        }
                    )
                    .setTimestamp();
                
                await interaction.reply({
                    embeds: [embed],
                    ephemeral: true
                });
                
            } else if (subcommand === 'enable') {
                configManager.setResponseEnabled(true);
                await interaction.reply({
                    content: '✅ Bot responses enabled',
                    ephemeral: true
                });
                
            } else if (subcommand === 'disable') {
                configManager.setResponseEnabled(false);
                await interaction.reply({
                    content: '❌ Bot responses disabled',
                    ephemeral: true
                });
            }
            
        } catch (error) {
            console.error('Error in config command:', error);
            await interaction.reply({
                content: '❌ An error occurred while processing the command.',
                ephemeral: true
            });
        }
    },
};

