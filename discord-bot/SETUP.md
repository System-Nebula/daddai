# Discord Bot Setup Guide

## Quick Start

### 1. Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Name it (e.g., "RAG Bot")
4. Go to "Bot" section
5. Click "Add Bot" → "Yes, do it!"
6. Under "Privileged Gateway Intents", enable:
   - ✅ MESSAGE CONTENT INTENT (required!)
7. Copy the bot token (click "Reset Token" if needed)
8. Go to "OAuth2" → "URL Generator"
9. Select scopes:
   - ✅ bot
   - ✅ applications.commands
10. Select bot permissions:
    - ✅ Send Messages
    - ✅ Read Message History
    - ✅ Use Slash Commands
11. Copy the generated URL and open it in browser to invite bot to your server

### 2. Configure Bot

1. Copy `.env.example` to `.env`:
   ```bash
   cd discord-bot
   copy .env.example .env
   ```

2. Edit `.env` and add your Discord token:
   ```
   DISCORD_TOKEN=your_token_here
   PYTHON_PATH=python
   DEBUG=false
   ```

### 3. Test RAG API

Make sure the Python RAG API works:
```bash
python rag_api.py --question "test question"
```

Should return JSON with an answer.

### 4. Start the Bot

```bash
cd discord-bot
npm start
```

You should see:
```
✅ Bot is ready! Logged in as YourBot#1234
📚 RAG system initialized
```

### 5. Use the Bot

In Discord:
- `/rag What are Space Marines?` - Ask a question
- `@YourBot What are Space Marines?` - Mention bot with question
- `!rag What are Space Marines?` - Prefix command
- `/clear` - Clear your conversation history

## Troubleshooting

### "Bot is ready" but doesn't respond
- Check bot has "Message Content Intent" enabled
- Verify bot has permissions in your server
- Check `.env` file has correct token

### "RAG service error"
- Test Python API: `python rag_api.py --question "test"`
- Check Neo4j is running
- Check LMStudio is running
- Verify `PYTHON_PATH` in `.env` is correct

### Conversation not saving
- Verify Neo4j is running and accessible
- Check RAG server is running (conversations are stored via RAG server)
- Check bot logs for Neo4j connection errors

## Features

✅ **Per-user memory**: Each user's conversations are stored separately
✅ **Context-aware**: Uses previous conversation when answering
✅ **Multiple ways to interact**: Slash commands, mentions, prefix commands
✅ **RAG integration**: Queries your Neo4j documents

## Next Steps

- Customize bot responses in `index.js`
- Adjust conversation memory in `conversationManager.js`
- Modify RAG parameters in `rag_api.py`

