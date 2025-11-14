# Discord Bot Commands Reference

This document lists all slash commands registered by the bot during startup.

## Commands Overview

The bot registers **5 main commands** with various subcommands and options:

---

## 1. `/admin` - Admin Commands

**Description:** Admin commands for managing user memories  
**Permission Required:** Administrator

### Subcommands:

#### `/admin users`
- **Description:** List all users with memory counts
- **Usage:** `/admin users`
- **Output:** Shows a list of all users who have stored memories with their memory counts

#### `/admin memories`
- **Description:** View a user's memories
- **Usage:** `/admin memories [user: @mention] [username: string]`
- **Options:**
  - `user` (optional): User to view memories for (by mention)
  - `username` (optional): Username to search for (alternative to user mention)
- **Output:** Displays user memories with pagination (embeds with buttons)

#### `/admin documents`
- **Description:** List all shared documents
- **Usage:** `/admin documents`
- **Output:** Shows a list of all documents uploaded to the shared knowledge base

---

## 2. `/rag` - RAG Query

**Description:** Query the RAG system with a question  
**Permission Required:** None (all users)

### Options:
- `question` (required): Your question about the documents

### Usage:
```
/rag question: "What is the main topic of the uploaded documents?"
```

### Behavior:
- Queries the RAG system with the question
- Uses conversation history for context
- Stores the conversation turn
- Returns the answer from the RAG system

---

## 3. `/clear` - Clear Conversation

**Description:** Clear your conversation history  
**Permission Required:** None (all users)

### Usage:
```
/clear
```

### Behavior:
- Clears the user's short-term conversation history
- Does NOT delete long-term memories
- Response is ephemeral (only visible to the user)

---

## 4. `/config` - Bot Configuration

**Description:** Configure bot settings (Admin only)  
**Permission Required:** Administrator

### Subcommands:

#### `/config channel`
- **Description:** Set the channel where the bot responds
- **Usage:** `/config channel [channel: #channel]`
- **Options:**
  - `channel` (optional): Channel for bot responses (leave empty to allow all)
- **Behavior:**
  - If channel specified: Bot only responds in that channel
  - If no channel: Bot responds in all channels

#### `/config status`
- **Description:** View current bot configuration
- **Usage:** `/config status`
- **Output:** Shows current response channel and enabled/disabled status

#### `/config enable`
- **Description:** Enable bot responses
- **Usage:** `/config enable`
- **Behavior:** Enables bot responses (if previously disabled)

#### `/config disable`
- **Description:** Disable bot responses
- **Usage:** `/config disable`
- **Behavior:** Disables bot responses globally

---

## 5. `/upload` - Upload Document

**Description:** Upload a document to the shared knowledge base  
**Permission Required:** None (all users)

### Options:
- `file` (required): PDF, DOCX, or text file to upload

### Supported File Types:
- `.pdf` - PDF documents
- `.docx` - Microsoft Word documents
- `.doc` - Legacy Word documents
- `.txt` - Plain text files
- `.md` - Markdown files

### File Size Limit:
- Maximum: 25MB

### Usage:
```
/upload file: [attach file]
```

### Behavior:
- Downloads the file from Discord
- Processes it using Docling
- Stores it in the shared knowledge base (accessible to all users)
- Returns confirmation message

---

## Command Registration Process

During startup, the bot:

1. **Scans** `discord-bot/src/commands/` directory for `.js` files (excluding `deploy.js`)
2. **Loads** each command file and extracts the `data` property
3. **Clears** all existing commands for the guild (ID: `549642809574162458`)
4. **Registers** all new commands via Discord API
5. **Logs** the registration process with command names and descriptions

### Files Scanned:
- `admin.js` → `/admin` command
- `rag.js` → `/rag` command
- `clear.js` → `/clear` command
- `config.js` → `/config` command
- `upload.js` → `/upload` command
- `deploy.js` → **EXCLUDED** (deployment script, not a command)

---

## Auto-Detection Features

The bot also has **auto-detection** features that work without slash commands:

### Document Upload Detection
- Automatically detects when users upload files (PDF, DOCX, TXT, MD)
- Processes and stores them in the shared knowledge base
- Works in the configured channel (or all channels if none configured)

### Question Detection
- Automatically detects when users ask questions (mention bot or direct message)
- Uses RAG system for document-related questions
- Uses simple chat for general questions
- Stores important information as long-term memories

---

## Notes

- All commands are registered as **guild-specific** commands (not global)
- Commands are cleared and re-registered every time the bot starts
- The bot automatically detects its CLIENT_ID from the token
- Admin commands require Administrator permissions
- Regular users can use `/rag`, `/clear`, and `/upload` without special permissions

