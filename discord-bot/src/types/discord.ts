/**
 * Type definitions for Discord.js interactions and events
 */

import type {
    Message,
    ChatInputCommandInteraction,
    ButtonInteraction,
    StringSelectMenuInteraction,
    Guild,
    TextChannel,
    User,
    GuildMember,
    Attachment,
    EmbedBuilder,
    ActionRowBuilder,
    ButtonBuilder,
    AttachmentBuilder,
    Collection,
} from 'discord.js';

export interface DiscordMessage extends Message {
    content: string;
    author: User;
    channel: TextChannel;
    guild: Guild | null;
    attachments: Collection<string, Attachment>;
    member: GuildMember | null;
}

export interface CommandContext {
    message?: Message;
    interaction?: ChatInputCommandInteraction | ButtonInteraction | StringSelectMenuInteraction;
    user: User;
    channel: TextChannel;
    guild: Guild | null;
    member: GuildMember | null;
}

export interface CommandResponse {
    content?: string;
    embeds?: EmbedBuilder[];
    components?: ActionRowBuilder<ButtonBuilder>[];
    files?: AttachmentBuilder[];
    ephemeral?: boolean;
}

export type CommandHandler = (context: CommandContext) => Promise<CommandResponse | void>;

export interface CommandDefinition {
    name: string;
    description: string;
    handler: CommandHandler;
    options?: Array<{
        name: string;
        description: string;
        type: number;
        required?: boolean;
    }>;
}

