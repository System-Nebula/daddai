import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface BotConfig {
    botChannelId: string | null;  // null = respond in all channels
    responseEnabled: boolean;
}

class ConfigManager {
    private configPath: string;
    private config: BotConfig;

    constructor() {
        // Use ES module __dirname
        const dirname = __dirname;
        this.configPath = path.join(dirname, '..', 'data', 'config.json');
        this.ensureDataDirectory();
        this.config = this.loadConfig();
    }

    private ensureDataDirectory(): void {
        const dataDir = path.dirname(this.configPath);
        if (!fs.existsSync(dataDir)) {
            fs.mkdirSync(dataDir, { recursive: true });
        }
    }

    private loadConfig(): BotConfig {
        if (fs.existsSync(this.configPath)) {
            try {
                const data = fs.readFileSync(this.configPath, 'utf8');
                return JSON.parse(data) as BotConfig;
            } catch (error) {
                console.error('Error loading config:', error);
                return this.getDefaultConfig();
            }
        }
        return this.getDefaultConfig();
    }

    private getDefaultConfig(): BotConfig {
        return {
            botChannelId: null,  // null = respond in all channels
            responseEnabled: true
        };
    }

    saveConfig(): boolean {
        try {
            fs.writeFileSync(this.configPath, JSON.stringify(this.config, null, 2));
            return true;
        } catch (error) {
            console.error('Error saving config:', error);
            return false;
        }
    }

    setBotChannel(channelId: string | null): boolean {
        this.config.botChannelId = channelId;
        return this.saveConfig();
    }

    getBotChannel(): string | null {
        return this.config.botChannelId;
    }

    isChannelAllowed(channelId: string): boolean {
        // If no channel set, allow all channels
        if (!this.config.botChannelId) {
            return true;
        }
        return channelId === this.config.botChannelId;
    }

    setResponseEnabled(enabled: boolean): boolean {
        this.config.responseEnabled = enabled;
        return this.saveConfig();
    }

    isResponseEnabled(): boolean {
        return this.config.responseEnabled !== false;
    }
}

export default ConfigManager;

