import { SlashCommandBuilder, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, type ChatInputCommandInteraction, type ButtonInteraction } from 'discord.js';
import type ConversationManager from '../conversationManager.js';
import type PersistentRAGService from '../ragServicePersistent.js';
import type { default as MemoryService } from '../memoryService.js';
import type DocumentService from '../documentService.js';
import type ConfigManager from '../configManager.js';

interface ChannelInfo {
    channel_id: string;
    channel_name?: string;
    memory_count: number;
    last_active?: string;
}

interface ChannelsResponse {
    channels?: ChannelInfo[];
}

interface MemoryInfo {
    content: string;
    memory_type: string;
    created_at?: string;
}

interface MemoriesResponse {
    memories?: MemoryInfo[];
    count?: number;
}

interface DocumentInfo {
    file_name: string;
    chunk_count?: number;
    uploaded_by?: string;
    uploaded_at?: string;
}

interface DocumentsResponse {
    documents?: DocumentInfo[];
}

export default {
    data: new SlashCommandBuilder()
        .setName('admin')
        .setDescription('Admin commands for managing channel memories')
        .addSubcommand(subcommand =>
            subcommand
                .setName('channels')
                .setDescription('List all channels with memory counts'))
        .addSubcommand(subcommand =>
            subcommand
                .setName('memories')
                .setDescription('View a channel\'s memories')
                .addChannelOption(option =>
                    option
                        .setName('channel')
                        .setDescription('Channel to view memories for')
                        .setRequired(false))
                .addStringOption(option =>
                    option
                        .setName('channelname')
                        .setDescription('Channel name to search for (alternative to channel mention)')
                        .setRequired(false)))
        .addSubcommand(subcommand =>
            subcommand
                .setName('documents')
                .setDescription('List all shared documents')),
    
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
            if (subcommand === 'channels') {
                await interaction.deferReply();
                
                const channels = await memoryService.getAllChannels() as ChannelsResponse;
                
                if (!channels.channels || channels.channels.length === 0) {
                    await interaction.editReply('No channels found.');
                    return;
                }
                
                // Create embed with channel list
                const embed = new EmbedBuilder()
                    .setTitle('📊 Channel Memory Statistics')
                    .setDescription('Channels with stored memories')
                    .setColor(0x5865F2)
                    .setTimestamp();
                
                // Add channels (limit to 25 for Discord embed limit)
                const channelList = channels.channels.slice(0, 25).map((channel, index) => {
                    const lastActive = channel.last_active ? new Date(channel.last_active).toLocaleDateString() : 'Never';
                    return `**${index + 1}.** <#${channel.channel_id}> (${channel.channel_name || 'Unknown'})\n   Memories: ${channel.memory_count} | Last Active: ${lastActive}`;
                }).join('\n\n');
                
                embed.setDescription(channelList);
                
                await interaction.editReply({ embeds: [embed] });
                
            } else if (subcommand === 'memories') {
                await interaction.deferReply();
                
                const targetChannel = interaction.options.getChannel('channel');
                const channelNameSearch = interaction.options.getString('channelname');
                
                let channelId: string | null = null;
                let displayName = 'Unknown Channel';
                
                if (targetChannel) {
                    // Use Discord channel object (most reliable - uses channel ID)
                    channelId = targetChannel.id;
                    displayName = targetChannel.name || 'Unknown';
                } else if (channelNameSearch) {
                    // Search by channel name string
                    displayName = channelNameSearch;
                } else {
                    await interaction.editReply('Please provide either a channel mention or channel name to search for.');
                    return;
                }
                
                // Get memories (by channel ID if available, otherwise by channel name)
                const memories = await memoryService.getChannelMemories(
                    channelId || null,
                    50,
                    channelId ? null : channelNameSearch || null
                ) as MemoriesResponse;
                
                if (!memories.memories || memories.memories.length === 0) {
                    await interaction.editReply(`No memories found for ${displayName}.`);
                    return;
                }
                
                // Create paginated embeds
                const pages: EmbedBuilder[] = [];
                const memoriesPerPage = 5;
                
                for (let i = 0; i < memories.memories.length; i += memoriesPerPage) {
                    const pageMemories = memories.memories.slice(i, i + memoriesPerPage);
                    
                    const embed = new EmbedBuilder()
                        .setTitle(`💭 Memories for ${displayName}`)
                        .setDescription(`Page ${Math.floor(i / memoriesPerPage) + 1} of ${Math.ceil(memories.memories.length / memoriesPerPage)}`)
                        .setColor(0x5865F2)
                        .setFooter({ text: `Total: ${memories.count || 0} memories` })
                        .setTimestamp();
                    
                    pageMemories.forEach((memory, index) => {
                        const date = memory.created_at ? new Date(memory.created_at).toLocaleString() : 'Unknown';
                        embed.addFields({
                            name: `${i + index + 1}. [${memory.memory_type}] ${date}`,
                            value: memory.content.substring(0, 1024) || 'No content',
                            inline: false
                        });
                    });
                    
                    pages.push(embed);
                }
                
                // Send first page with navigation buttons
                let currentPage = 0;
                const row = new ActionRowBuilder<ButtonBuilder>()
                    .addComponents(
                        new ButtonBuilder()
                            .setCustomId('prev_memory')
                            .setLabel('◀ Previous')
                            .setStyle(ButtonStyle.Primary)
                            .setDisabled(true),
                        new ButtonBuilder()
                            .setCustomId('next_memory')
                            .setLabel('Next ▶')
                            .setStyle(ButtonStyle.Primary)
                            .setDisabled(pages.length <= 1)
                    );
                
                const message = await interaction.editReply({
                    embeds: [pages[0]],
                    components: pages.length > 1 ? [row] : []
                });
                
                // Handle button interactions
                if (pages.length > 1 && message) {
                    const collector = message.createMessageComponentCollector({ time: 60000 });
                    
                    collector.on('collect', async (buttonInteraction: ButtonInteraction) => {
                        if (buttonInteraction.user.id !== interaction.user.id) {
                            await buttonInteraction.reply({
                                content: 'This is not your menu!',
                                ephemeral: true
                            });
                            return;
                        }
                        
                        if (buttonInteraction.customId === 'prev_memory') {
                            currentPage = Math.max(0, currentPage - 1);
                        } else if (buttonInteraction.customId === 'next_memory') {
                            currentPage = Math.min(pages.length - 1, currentPage + 1);
                        }
                        
                        const newRow = new ActionRowBuilder<ButtonBuilder>()
                            .addComponents(
                                new ButtonBuilder()
                                    .setCustomId('prev_memory')
                                    .setLabel('◀ Previous')
                                    .setStyle(ButtonStyle.Primary)
                                    .setDisabled(currentPage === 0),
                                new ButtonBuilder()
                                    .setCustomId('next_memory')
                                    .setLabel('Next ▶')
                                    .setStyle(ButtonStyle.Primary)
                                    .setDisabled(currentPage === pages.length - 1)
                            );
                        
                        await buttonInteraction.update({
                            embeds: [pages[currentPage]],
                            components: [newRow]
                        });
                    });
                }
                
            } else if (subcommand === 'documents') {
                await interaction.deferReply();
                
                try {
                    const documents = await documentService.getAllDocuments() as DocumentsResponse;
                    
                    if (!documents.documents || documents.documents.length === 0) {
                        await interaction.editReply('No shared documents found.');
                        return;
                    }
                    
                    const embed = new EmbedBuilder()
                        .setTitle('📚 Shared Documents')
                        .setDescription('Documents available to all users')
                        .setColor(0x5865F2)
                        .setTimestamp();
                    
                    const docList = documents.documents.map((doc, index) => {
                        const uploadedBy = doc.uploaded_by ? `<@${doc.uploaded_by}>` : 'Unknown';
                        const date = doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleDateString() : 'Unknown';
                        return `**${index + 1}.** ${doc.file_name}\n   Chunks: ${doc.chunk_count || 0} | Uploaded by: ${uploadedBy} | ${date}`;
                    }).join('\n\n');
                    
                    embed.setDescription(docList.substring(0, 4096));
                    
                    await interaction.editReply({ embeds: [embed] });
                } catch (error) {
                    console.error('Error getting documents:', error);
                    await interaction.editReply('Error retrieving documents.');
                }
            }
            
        } catch (error) {
            console.error('Error in admin command:', error);
            const errorMsg = interaction.deferred ? 'editReply' : 'reply';
            await (interaction as { [key: string]: (options: { content: string; ephemeral: boolean }) => Promise<unknown> })[errorMsg]({
                content: '❌ An error occurred while processing the command.',
                ephemeral: true
            });
        }
    },
};

