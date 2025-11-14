# Discord RAG Bot

A Discord bot that uses your RAG system to answer questions about your documents, with per-user conversation memory.

## Features

- 🤖 **RAG Integration**: Answers questions using your ingested documents
- 💬 **Conversation Memory**: Remembers each user's conversation history
- 🔍 **Context-Aware**: Uses previous conversation context when answering
- 📚 **Document Queries**: Query your Neo4j-stored documents via Discord
- 📄 **Auto-Detection**: Automatically detects document uploads and questions (no slash commands needed!)
- ⚙️ **Channel Configuration**: Admins can restrict bot to specific channels
- 🧠 **Long-Term Memory**: Stores important conversations for future reference
- 📖 **Shared Documents**: Upload documents that are accessible to all users

## Setup

### 1. Install Dependencies

```bash
cd discord-bot
npm install
```

### 2. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section
4. Create a bot and copy the token
5. Enable "Message Content Intent" under Privileged Gateway Intents
6. Invite bot to your server with these permissions:
   - Send Messages
   - Read Message History
   - Use Slash Commands

### 3. Configure Environment

Copy `.env.example` to `.env` and fill in your Discord token:

```bash
cp .env.example .env
```

Edit `.env`:
```env
DISCORD_TOKEN=your_discord_bot_token_here
PYTHON_PATH=python
DEBUG=false
```

**Note:** The CLIENT_ID is automatically detected from your bot token - no need to set it manually!

### 4. Deploy Slash Commands

Before starting the bot, deploy the slash commands to your server:

```bash
npm run deploy
```

This will:
- Clear all existing commands for your server (ID: 181668952420646912)
- Register the new commands: `/config`, `/admin`, `/rag`, `/upload`, `/clear`

**Note:** The deploy script is configured for server ID `181668952420646912`. To change it, edit `discord-bot/src/commands/deploy.js` and update the `GUILD_ID` constant.

### 5. Start the Bot

Make sure:
- ✅ Neo4j is running
- ✅ LMStudio is running with a model loaded
- ✅ Documents are ingested in the RAG system

Then start the bot:
```bash
npm start
```

The web interface will automatically start at `http://localhost:3000` (or the port specified in `WEB_PORT` environment variable).

## Usage

### For Regular Users

**No slash commands needed!** The bot automatically detects:

1. **Document Uploads**: Just attach a PDF, DOCX, or text file to a message
   - Supported formats: `.pdf`, `.docx`, `.doc`, `.txt`, `.md`
   - Maximum size: 25MB
   - Documents are automatically processed and shared with all users

2. **Questions**: Ask questions naturally:
   - Messages with `?` that are at least 10 characters long
   - Messages that mention the bot (`@YourBot`)
   - The bot will automatically respond with RAG-powered answers

### Admin Commands (Slash Commands)

**Configuration:**
- `/config channel [channel]` - Set which channel the bot responds in (leave empty to allow all channels)
- `/config status` - View current bot configuration
- `/config enable` - Enable bot responses
- `/config disable` - Disable bot responses

**Management:**
- `/admin users` - List all users with memory counts
- `/admin memories <user>` - View a user's stored memories
- `/admin documents` - List all shared documents

### Optional Commands

- `/rag <question>` - Ask a question (alternative to auto-detection)
- `/upload <file>` - Upload a document (alternative to auto-detection)
- `/clear` - Clear your conversation history

### Conversation Memory

The bot remembers each user's conversation history and uses it to provide context-aware answers. Each user's conversation is stored separately in `discord-bot/data/conversations/`.

### Channel Configuration

By default, the bot responds in all channels. Admins can restrict the bot to a specific channel using:
```
/config channel #your-channel
```

To allow the bot in all channels again:
```
/config channel
```

### Long-Term Memory

Important conversations are automatically stored as long-term memories in Neo4j. These memories are retrieved when relevant to future questions, allowing the bot to reference past conversations.

## How It Works

1. **User asks a question** via Discord
2. **Bot retrieves** user's conversation history
3. **RAG system queries** your documents with context
4. **Bot responds** with the answer
5. **Conversation is saved** for future context

## File Structure

```
discord-bot/
├── index.js              # Main bot file
├── src/
│   ├── ragService.js     # RAG integration service
│   ├── conversationManager.js  # Conversation memory
│   ├── memoryService.js  # Long-term memory service
│   ├── documentService.js # Shared document service
│   ├── configManager.js  # Channel configuration
│   └── commands/         # Slash commands
│       ├── rag.js
│       ├── clear.js
│       ├── upload.js
│       ├── admin.js
│       └── config.js
├── data/
│   ├── conversations/    # User conversation files
│   └── config.json       # Bot configuration (channel settings)
└── package.json
```

## Troubleshooting

### Bot doesn't respond
- Check that `DISCORD_TOKEN` is correct
- Ensure bot has "Message Content Intent" enabled
- Check bot has permissions in your server

### RAG errors
- Verify Python RAG system is working: `python rag_api.py --question "test"`
- Check Neo4j is running
- Check LMStudio is running

### Conversation not working
- Check `discord-bot/data/conversations/` directory exists
- Verify file permissions

## Advanced Configuration

### Adjust RAG Parameters

Edit `rag_api.py` to change:
- `top_k`: Number of chunks retrieved
- `max_tokens`: Response length

### Conversation History Limit

Edit `conversationManager.js`:
- Change `slice(-50)` to adjust how many messages are kept

## Development

Run in development mode:
```bash
npm start
```

The bot will log all activity to console.

