import { describe, it } from 'node:test';
import assert from 'node:assert';
import ConfigManager from './configManager.js';

describe('ConfigManager', () => {
    it('should create a ConfigManager instance', () => {
        const configManager = new ConfigManager();
        assert.ok(configManager);
    });

    it('should have default config values', () => {
        const configManager = new ConfigManager();
        assert.strictEqual(configManager.isResponseEnabled(), true);
        assert.strictEqual(configManager.getBotChannel(), null);
    });

    it('should allow all channels when no channel is set', () => {
        const configManager = new ConfigManager();
        assert.strictEqual(configManager.isChannelAllowed('123456789'), true);
    });

    it('should set and get bot channel', () => {
        const configManager = new ConfigManager();
        const channelId = '123456789';
        configManager.setBotChannel(channelId);
        assert.strictEqual(configManager.getBotChannel(), channelId);
    });

    it('should only allow the set channel', () => {
        const configManager = new ConfigManager();
        const channelId = '123456789';
        configManager.setBotChannel(channelId);
        assert.strictEqual(configManager.isChannelAllowed(channelId), true);
        assert.strictEqual(configManager.isChannelAllowed('987654321'), false);
    });

    it('should set and get response enabled', () => {
        const configManager = new ConfigManager();
        configManager.setResponseEnabled(false);
        assert.strictEqual(configManager.isResponseEnabled(), false);
        configManager.setResponseEnabled(true);
        assert.strictEqual(configManager.isResponseEnabled(), true);
    });
});

