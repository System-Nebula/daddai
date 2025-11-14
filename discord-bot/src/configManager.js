const fs = require('fs');
const path = require('path');

class ConfigManager {
    constructor() {
        this.configPath = path.join(__dirname, '..', 'data', 'config.json');
        this.ensureDataDirectory();
        this.config = this.loadConfig();
    }

    ensureDataDirectory() {
        const dataDir = path.join(__dirname, '..', 'data');
        if (!fs.existsSync(dataDir)) {
            fs.mkdirSync(dataDir, { recursive: true });
        }
    }

    loadConfig() {
        if (fs.existsSync(this.configPath)) {
            try {
                const data = fs.readFileSync(this.configPath, 'utf8');
                return JSON.parse(data);
            } catch (error) {
                console.error('Error loading config:', error);
                return this.getDefaultConfig();
            }
        }
        return this.getDefaultConfig();
    }

    getDefaultConfig() {
        return {
            botChannelId: null,  // null = respond in all channels
            responseEnabled: true
        };
    }

    saveConfig() {
        try {
            fs.writeFileSync(this.configPath, JSON.stringify(this.config, null, 2));
            return true;
        } catch (error) {
            console.error('Error saving config:', error);
            return false;
        }
    }

    setBotChannel(channelId) {
        this.config.botChannelId = channelId;
        return this.saveConfig();
    }

    getBotChannel() {
        return this.config.botChannelId;
    }

    isChannelAllowed(channelId) {
        // If no channel set, allow all channels
        if (!this.config.botChannelId) {
            return true;
        }
        return channelId === this.config.botChannelId;
    }

    setResponseEnabled(enabled) {
        this.config.responseEnabled = enabled;
        return this.saveConfig();
    }

    isResponseEnabled() {
        return this.config.responseEnabled !== false;
    }
}

module.exports = ConfigManager;

