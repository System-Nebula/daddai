import { SlashCommandBuilder, EmbedBuilder, REST, Routes, type ChatInputCommandInteraction } from 'discord.js';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import logger from '../logger.js';

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
        .setName('sync')
        .setDescription('Sync slash commands to the test guild (Admin only)'),
    
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
        
        await interaction.deferReply({ ephemeral: true });
        
        try {
            const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN as string);
            
            // Get application info
            const application = await rest.get(Routes.oauth2CurrentApplication()) as { id: string };
            const CLIENT_ID = application.id;
            
            // Load commands
            const commands: unknown[] = [];
            const commandsPath = path.join(__dirname, '..');
            const commandFiles = fs.readdirSync(commandsPath).filter(file => 
                (file.endsWith('.js') || file.endsWith('.ts')) && file !== 'deploy.js' && file !== 'deploy.ts' && file !== 'sync.js' && file !== 'sync.ts'
            );
            
            for (const file of commandFiles) {
                try {
                    // Use dynamic import for ES modules
                    const filePath = path.join(commandsPath, file);
                    const command = await import(filePath);
                    const commandModule = command.default || command;
                    if ('data' in commandModule) {
                        commands.push(commandModule.data.toJSON());
                    }
                } catch (error) {
                    logger.warn(`Failed to load command ${file}:`, { error: (error as Error).message });
                }
            }
            
            // Always sync to test guild only
            const TEST_GUILD_ID = '549642809574162458';
            const guild = interaction.client.guilds.cache.get(TEST_GUILD_ID);
            
            if (!guild) {
                await interaction.editReply({
                    content: `❌ Test guild ${TEST_GUILD_ID} not found. Make sure the bot is in the test server.`,
                });
                return;
            }
            
            const statusMessages: string[] = [];
            
            // Step 1: Clear global commands (from previous bot version)
            statusMessages.push('🔄 Step 1: Clearing global commands...');
            try {
                const globalCommands = await rest.get(Routes.applicationCommands(CLIENT_ID)) as Array<{ id: string; name: string }>;
                if (globalCommands && globalCommands.length > 0) {
                    statusMessages.push(`   Found ${globalCommands.length} global command(s) to remove`);
                    for (const cmd of globalCommands) {
                        try {
                            await rest.delete(Routes.applicationCommand(CLIENT_ID, cmd.id));
                            statusMessages.push(`   ✅ Deleted: /${cmd.name}`);
                        } catch (error) {
                            const err = error as Error;
                            statusMessages.push(`   ⚠️  Error deleting /${cmd.name}: ${err.message}`);
                        }
                        await new Promise(resolve => setTimeout(resolve, 200));
                    }
                } else {
                    statusMessages.push(`   ✅ No global commands found`);
                }
            } catch (error) {
                const err = error as Error;
                statusMessages.push(`   ⚠️  Error fetching global commands: ${err.message}`);
            }
            
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Step 2: Clear guild commands
            statusMessages.push(`🔄 Step 2: Clearing guild commands...`);
            try {
                const guildCommands = await rest.get(Routes.applicationGuildCommands(CLIENT_ID, TEST_GUILD_ID)) as Array<{ id: string; name: string }>;
                if (guildCommands && guildCommands.length > 0) {
                    statusMessages.push(`   Found ${guildCommands.length} guild command(s) to remove`);
                }
                await rest.put(
                    Routes.applicationGuildCommands(CLIENT_ID, TEST_GUILD_ID),
                    { body: [] }
                );
                statusMessages.push(`   ✅ Cleared guild commands`);
            } catch (error) {
                const err = error as Error;
                statusMessages.push(`   ⚠️  Error clearing guild commands: ${err.message}`);
            }
            
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Step 3: Register new commands
            statusMessages.push(`🔄 Step 3: Registering ${commands.length} commands...`);
            const registeredCommands = await rest.put(
                Routes.applicationGuildCommands(CLIENT_ID, TEST_GUILD_ID),
                { body: commands }
            ) as Array<{ id: string; name: string }>;
            statusMessages.push(`   ✅ Registered ${registeredCommands.length} command(s)`);
            
            // Step 4: Verify
            statusMessages.push(`🔄 Step 4: Verifying...`);
            try {
                const verifyCommands = await rest.get(Routes.applicationGuildCommands(CLIENT_ID, TEST_GUILD_ID)) as Array<{ id: string; name: string }>;
                statusMessages.push(`   ✅ Verified: ${verifyCommands.length} command(s) registered`);
            } catch (error) {
                const err = error as Error;
                statusMessages.push(`   ⚠️  Verification error: ${err.message}`);
            }
            
            const embed = new EmbedBuilder()
                .setTitle('✅ Commands Synced to Test Guild')
                .setDescription(`Successfully synced ${commands.length} commands to ${guild.name}`)
                .setColor(0x5865F2)
                .addFields({
                    name: 'Registered Commands',
                    value: commands.map((cmd: { name?: string }) => `\`/${cmd.name || 'unknown'}\``).join(', ') || 'None',
                    inline: false
                })
                .addFields({
                    name: 'Sync Details',
                    value: statusMessages.join('\n').substring(0, 1024) || 'Sync completed',
                    inline: false
                })
                .setFooter({ text: `Guild ID: ${TEST_GUILD_ID} | Commands sync to this guild only` })
                .setTimestamp();
            
            await interaction.editReply({ embeds: [embed] });
        } catch (error) {
            const err = error as Error;
            console.error('Error syncing commands:', error);
            await interaction.editReply({
                content: `❌ Error syncing commands: ${err.message}`,
            });
        }
    },
};

