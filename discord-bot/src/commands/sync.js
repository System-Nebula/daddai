const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const { REST, Routes } = require('discord.js');
const fs = require('fs');
const path = require('path');
const logger = require('../logger');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('sync')
        .setDescription('Sync slash commands to the test guild (Admin only)'),
    
    async execute(interaction, conversationManager, ragService, memoryService, documentService, configManager) {
        // Check if user has admin role
        if (!interaction.member.permissions.has('Administrator')) {
            await interaction.reply({
                content: '❌ You need administrator permissions to use this command.',
                ephemeral: true
            });
            return;
        }
        
        await interaction.deferReply({ ephemeral: true });
        
        try {
            const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);
            
            // Get application info
            const application = await rest.get(Routes.oauth2CurrentApplication());
            const CLIENT_ID = application.id;
            
            // Load commands
            const commands = [];
            const commandsPath = path.join(__dirname);
            const commandFiles = fs.readdirSync(commandsPath).filter(file => 
                file.endsWith('.js') && file !== 'deploy.js' && file !== 'sync.js'
            );
            
            for (const file of commandFiles) {
                const command = require(path.join(commandsPath, file));
                if ('data' in command) {
                    commands.push(command.data.toJSON());
                }
            }
            
            // Always sync to test guild only
            const TEST_GUILD_ID = '549642809574162458';
            const guild = interaction.client.guilds.cache.get(TEST_GUILD_ID);
            
            if (!guild) {
                await interaction.editReply({
                    content: `❌ Test guild ${TEST_GUILD_ID} not found. Make sure the bot is in the test server.`,
                    ephemeral: true
                });
                return;
            }
            
            const statusMessages = [];
            
            // Step 1: Clear global commands (from previous bot version)
            statusMessages.push('🔄 Step 1: Clearing global commands...');
            try {
                const globalCommands = await rest.get(Routes.applicationCommands(CLIENT_ID));
                if (globalCommands && globalCommands.length > 0) {
                    statusMessages.push(`   Found ${globalCommands.length} global command(s) to remove`);
                    for (const cmd of globalCommands) {
                        try {
                            await rest.delete(Routes.applicationCommand(CLIENT_ID, cmd.id));
                            statusMessages.push(`   ✅ Deleted: /${cmd.name}`);
                        } catch (error) {
                            statusMessages.push(`   ⚠️  Error deleting /${cmd.name}: ${error.message}`);
                        }
                        await new Promise(resolve => setTimeout(resolve, 200));
                    }
                } else {
                    statusMessages.push(`   ✅ No global commands found`);
                }
            } catch (error) {
                statusMessages.push(`   ⚠️  Error fetching global commands: ${error.message}`);
            }
            
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Step 2: Clear guild commands
            statusMessages.push(`🔄 Step 2: Clearing guild commands...`);
            try {
                const guildCommands = await rest.get(Routes.applicationGuildCommands(CLIENT_ID, TEST_GUILD_ID));
                if (guildCommands && guildCommands.length > 0) {
                    statusMessages.push(`   Found ${guildCommands.length} guild command(s) to remove`);
                }
                await rest.put(
                    Routes.applicationGuildCommands(CLIENT_ID, TEST_GUILD_ID),
                    { body: [] }
                );
                statusMessages.push(`   ✅ Cleared guild commands`);
            } catch (error) {
                statusMessages.push(`   ⚠️  Error clearing guild commands: ${error.message}`);
            }
            
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Step 3: Register new commands
            statusMessages.push(`🔄 Step 3: Registering ${commands.length} commands...`);
            const registeredCommands = await rest.put(
                Routes.applicationGuildCommands(CLIENT_ID, TEST_GUILD_ID),
                { body: commands }
            );
            statusMessages.push(`   ✅ Registered ${registeredCommands.length} command(s)`);
            
            // Step 4: Verify
            statusMessages.push(`🔄 Step 4: Verifying...`);
            try {
                const verifyCommands = await rest.get(Routes.applicationGuildCommands(CLIENT_ID, TEST_GUILD_ID));
                statusMessages.push(`   ✅ Verified: ${verifyCommands.length} command(s) registered`);
            } catch (error) {
                statusMessages.push(`   ⚠️  Verification error: ${error.message}`);
            }
            
            const embed = new EmbedBuilder()
                .setTitle('✅ Commands Synced to Test Guild')
                .setDescription(`Successfully synced ${commands.length} commands to ${guild.name}`)
                .setColor(0x5865F2)
                .addFields({
                    name: 'Registered Commands',
                    value: commands.map(cmd => `\`/${cmd.name}\``).join(', ') || 'None',
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
            console.error('Error syncing commands:', error);
            await interaction.editReply({
                content: `❌ Error syncing commands: ${error.message}`,
                ephemeral: true
            });
        }
    },
};

