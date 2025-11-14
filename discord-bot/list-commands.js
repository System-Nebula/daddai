const fs = require('fs');
const path = require('path');

const commandsPath = path.join(__dirname, 'src', 'commands');
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js') && file !== 'deploy.js');

console.log('\n╔══════════════════════════════════════════════════════════════╗');
console.log('║          REGISTERED DISCORD SLASH COMMANDS                  ║');
console.log('╚══════════════════════════════════════════════════════════════╝\n');

commandFiles.forEach((file, idx) => {
    try {
        const command = require(path.join(commandsPath, file));
        if (command.data) {
            const json = command.data.toJSON();
            console.log(`${idx + 1}. /${json.name.toUpperCase()}`);
            console.log(`   Description: ${json.description || 'No description'}`);
            
            if (json.options && json.options.length > 0) {
                console.log(`   Options:`);
                json.options.forEach(opt => {
                    if (opt.type === 1) { // SUB_COMMAND
                        console.log(`     └─ ${opt.name}`);
                        console.log(`        Description: ${opt.description || 'No description'}`);
                        if (opt.options && opt.options.length > 0) {
                            opt.options.forEach(subOpt => {
                                const required = subOpt.required ? '[REQUIRED]' : '[OPTIONAL]';
                                const typeName = getOptionType(subOpt.type);
                                console.log(`        • ${subOpt.name} (${typeName}): ${subOpt.description || ''} ${required}`);
                            });
                        }
                    } else {
                        const required = opt.required ? '[REQUIRED]' : '[OPTIONAL]';
                        const typeName = getOptionType(opt.type);
                        console.log(`     • ${opt.name} (${typeName}): ${opt.description || ''} ${required}`);
                    }
                });
            }
            console.log('');
        }
    } catch (error) {
        console.error(`Error loading ${file}:`, error.message);
    }
});

function getOptionType(type) {
    const types = {
        1: 'SUB_COMMAND',
        2: 'SUB_COMMAND_GROUP',
        3: 'STRING',
        4: 'INTEGER',
        5: 'BOOLEAN',
        6: 'USER',
        7: 'CHANNEL',
        8: 'ROLE',
        9: 'MENTIONABLE',
        10: 'NUMBER',
        11: 'ATTACHMENT'
    };
    return types[type] || `TYPE_${type}`;
}

console.log('╔══════════════════════════════════════════════════════════════╗');
console.log(`║  Total Commands: ${commandFiles.length.toString().padEnd(45)}║`);
console.log('╚══════════════════════════════════════════════════════════════╝\n');

