# Discord RAG Bot - Complete Setup

## ✅ What's Been Created

### Discord Bot Structure
```
discord-bot/
├── index.js                    # Main bot file
├── package.json                # Node.js dependencies
├── src/
│   ├── ragService.js          # RAG integration service
│   ├── conversationManager.js # Per-user conversation memory
│   └── commands/              # Slash commands
│       ├── rag.js            # /rag command
│       └── clear.js          # /clear command
├── data/                      # Conversation storage (auto-created)
│   └── conversations/        # User conversation files
└── README.md                  # Bot documentation
```

### Python Integration
- `rag_api.py` - API wrapper for Discord bot to call RAG system

## 🚀 Quick Start

### 1. Install Dependencies (Already Done ✅)
```bash
cd discord-bot
npm install
```

### 2. Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Create new application → Name it
3. Go to "Bot" → Add Bot
4. **IMPORTANT**: Enable "MESSAGE CONTENT INTENT" under Privileged Gateway Intents
5. Copy the bot token
6. Go to "OAuth2" → "URL Generator"
   - Select: `bot` and `applications.commands`
   - Permissions: Send Messages, Read Message History, Use Slash Commands
7. Copy URL and invite bot to your server

### 3. Configure Environment

Create `discord-bot/.env`:
```env
DISCORD_TOKEN=your_discord_bot_token_here
PYTHON_PATH=python
DEBUG=false
```

### 4. Start the Bot

```bash
cd discord-bot
npm start
```

## 💬 Usage

### Ways to Use the Bot

1. **Slash Command**: `/rag What are Space Marines?`
2. **Mention**: `@YourBot What are Space Marines?`
3. **Prefix**: `!rag What are Space Marines?`
4. **Clear History**: `/clear`

### Conversation Memory

- Each user's conversations are stored separately
- Bot remembers last 50 messages per user
- Uses conversation context when answering questions
- Files stored in `discord-bot/data/conversations/userId.json`

## 🔧 How It Works

1. **User asks question** → Discord message
2. **Bot retrieves** → User's conversation history
3. **RAG queries** → Your Neo4j documents with context
4. **Bot responds** → With answer from documents
5. **Saves conversation** → For future context

## 📋 Requirements

Before starting bot, ensure:
- ✅ Neo4j is running
- ✅ LMStudio is running with model loaded
- ✅ Documents are ingested: `python main.py ingest --path your_docs/`
- ✅ RAG API works: `python rag_api.py --question "test"`

## 🐛 Troubleshooting

### Bot doesn't respond
- Check "Message Content Intent" is enabled
- Verify bot has permissions in server
- Check `.env` file has correct token

### RAG errors
- Test: `python rag_api.py --question "test"`
- Verify Neo4j is running
- Verify LMStudio is running

### Path issues
- Ensure `rag_api.py` is in project root (same level as `discord-bot/`)
- Check `PYTHON_PATH` in `.env` points to correct Python

## 🎯 Features

✅ **Per-user memory** - Each user's conversations stored separately
✅ **Context-aware** - Uses previous conversation when answering
✅ **Multiple interfaces** - Slash commands, mentions, prefix commands
✅ **RAG integration** - Queries your Neo4j documents
✅ **Error handling** - Graceful error messages

## 📝 Next Steps

1. Create Discord bot and get token
2. Add token to `.env` file
3. Start bot: `npm start`
4. Test in Discord server!

The bot is ready to use! 🎉

# Discord RAG Bot - Complete Setup

## ✅ What's Been Created

### Discord Bot Structure
```
discord-bot/
├── index.js                    # Main bot file
├── package.json                # Node.js dependencies
├── src/
│   ├── ragService.js          # RAG integration service
│   ├── conversationManager.js # Per-user conversation memory
│   └── commands/              # Slash commands
│       ├── rag.js            # /rag command
│       └── clear.js          # /clear command
├── data/                      # Conversation storage (auto-created)
│   └── conversations/        # User conversation files
└── README.md                  # Bot documentation
```

### Python Integration
- `rag_api.py` - API wrapper for Discord bot to call RAG system

## 🚀 Quick Start

### 1. Install Dependencies (Already Done ✅)
```bash
cd discord-bot
npm install
```

### 2. Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Create new application → Name it
3. Go to "Bot" → Add Bot
4. **IMPORTANT**: Enable "MESSAGE CONTENT INTENT" under Privileged Gateway Intents
5. Copy the bot token
6. Go to "OAuth2" → "URL Generator"
   - Select: `bot` and `applications.commands`
   - Permissions: Send Messages, Read Message History, Use Slash Commands
7. Copy URL and invite bot to your server

### 3. Configure Environment

Create `discord-bot/.env`:
```env
DISCORD_TOKEN=your_discord_bot_token_here
PYTHON_PATH=python
DEBUG=false
```

### 4. Start the Bot

```bash
cd discord-bot
npm start
```

## 💬 Usage

### Ways to Use the Bot

1. **Slash Command**: `/rag What are Space Marines?`
2. **Mention**: `@YourBot What are Space Marines?`
3. **Prefix**: `!rag What are Space Marines?`
4. **Clear History**: `/clear`

### Conversation Memory

- Each user's conversations are stored separately
- Bot remembers last 50 messages per user
- Uses conversation context when answering questions
- Files stored in `discord-bot/data/conversations/userId.json`

## 🔧 How It Works

1. **User asks question** → Discord message
2. **Bot retrieves** → User's conversation history
3. **RAG queries** → Your Neo4j documents with context
4. **Bot responds** → With answer from documents
5. **Saves conversation** → For future context

## 📋 Requirements

Before starting bot, ensure:
- ✅ Neo4j is running
- ✅ LMStudio is running with model loaded
- ✅ Documents are ingested: `python main.py ingest --path your_docs/`
- ✅ RAG API works: `python rag_api.py --question "test"`

## 🐛 Troubleshooting

### Bot doesn't respond
- Check "Message Content Intent" is enabled
- Verify bot has permissions in server
- Check `.env` file has correct token

### RAG errors
- Test: `python rag_api.py --question "test"`
- Verify Neo4j is running
- Verify LMStudio is running

### Path issues
- Ensure `rag_api.py` is in project root (same level as `discord-bot/`)
- Check `PYTHON_PATH` in `.env` points to correct Python

## 🎯 Features

✅ **Per-user memory** - Each user's conversations stored separately
✅ **Context-aware** - Uses previous conversation when answering
✅ **Multiple interfaces** - Slash commands, mentions, prefix commands
✅ **RAG integration** - Queries your Neo4j documents
✅ **Error handling** - Graceful error messages

## 📝 Next Steps

1. Create Discord bot and get token
2. Add token to `.env` file
3. Start bot: `npm start`
4. Test in Discord server!

The bot is ready to use! 🎉

