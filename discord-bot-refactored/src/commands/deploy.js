const { REST, Routes } = require('discord.js');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

const commands = [];
const commandsPath = path.join(__dirname);
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js') && file !== 'deploy.js');

for (const file of commandFiles) {
    const command = require(path.join(commandsPath, file));
    if ('data' in command) {
        commands.push(command.data.toJSON());
    }
}

const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_TOKEN);

// Server ID - update this if needed
const GUILD_ID = '549642809574162458';

(async () => {
    try {
        if (!process.env.DISCORD_TOKEN) {
            console.error('❌ DISCORD_TOKEN not found in environment variables!');
            process.exit(1);
        }

        console.log('🔍 Fetching bot application info...');
        
        // Get the application info (including CLIENT_ID) from the token
        const application = await rest.get(Routes.oauth2CurrentApplication());
        const CLIENT_ID = application.id;
        
        console.log(`✅ Bot Application ID: ${CLIENT_ID}`);
        console.log(`✅ Bot Name: ${application.name}`);

        console.log(`\n🔄 Clearing existing commands for guild ${GUILD_ID}...`);
        
        // First, clear all existing commands for this guild
        try {
            await rest.put(
                Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID),
                { body: [] }
            );
            console.log('✅ Cleared all existing commands');
        } catch (error) {
            if (error.code === 10004) {
                console.error(`❌ Unknown Guild - Check that the GUILD_ID (${GUILD_ID}) is correct`);
                console.error('   Make sure the bot is in the server!');
                process.exit(1);
            }
            console.log('⚠️  No existing commands to clear (or error clearing):', error.message);
        }

        console.log(`\n📝 Registering ${commands.length} new application (/) commands...`);
        console.log('Commands to register:');
        commands.forEach((cmd, index) => {
            console.log(`  ${index + 1}. /${cmd.name}`);
        });

        // Register new commands for this specific guild
        const data = await rest.put(
            Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID),
            { body: commands },
        );

        console.log(`\n✅ Successfully registered ${data.length} application (/) commands for guild ${GUILD_ID}`);
        console.log('\nCommands registered:');
        data.forEach((cmd, index) => {
            console.log(`  ${index + 1}. /${cmd.name} - ${cmd.description || 'No description'}`);
        });
        
    } catch (error) {
        console.error('\n❌ Error deploying commands:', error.message);
        if (error.code === 50001) {
            console.error('   Missing Access - Make sure the bot is in the server and has proper permissions');
        } else if (error.code === 10004) {
            console.error(`   Unknown Guild - Check that the GUILD_ID (${GUILD_ID}) is correct`);
            console.error('   Make sure the bot is in the server!');
        } else if (error.code === 50035) {
            console.error('   Invalid Form Body - Check command definitions');
        } else if (error.status === 401) {
            console.error('   Unauthorized - Check that DISCORD_TOKEN is correct');
        }
        process.exit(1);
    }
})();

