# Discord Bot Integration with Enhanced RAG Pipeline

## Overview

The Discord bot has been updated to use the **Enhanced RAG Pipeline** with all intelligent features, including:
- Intelligent memory management
- User relations and context tracking
- Enhanced query understanding
- Action parsing (give, take, set, etc.)
- User state management
- Self-extending tools

## Changes Made

### 1. **RAG Server Integration** (`rag_server.py`)
- Updated to use `EnhancedRAGPipeline` instead of basic `RAGPipeline`
- Falls back to basic pipeline if enhanced is not available
- All enhanced features are now available to the Discord bot

### 2. **Command Sync Improvements** (`discord-bot/index.js`)
- Commands now sync automatically on bot startup (with 2-second delay for guild loading)
- Improved error handling and logging
- Commands sync to all guilds the bot is in
- Commands sync automatically when bot joins a new guild

### 3. **New Sync Command** (`/sync`)
- **Admin-only command** to manually sync commands
- Usage: `/sync` - Syncs commands to current server
- Usage: `/sync all:true` - Syncs commands to all servers
- Useful if commands don't sync automatically

### 4. **Enhanced RAG Command** (`/rag`)
- Now passes `channel_id` to enable enhanced memory and user relations
- Uses channel-based memories for better context
- Supports all enhanced features (actions, state queries, etc.)

## Available Commands

### Public Commands
- `/rag` - Query the RAG system with enhanced features
- `/upload` - Upload documents to shared knowledge base
- `/clear` - Clear conversation history

### Admin Commands
- `/admin channels` - List all channels with memory counts
- `/admin memories [channel]` - View channel memories
- `/admin documents` - List all shared documents
- `/config channel [channel]` - Set response channel
- `/config status` - View bot configuration
- `/config enable` - Enable bot responses
- `/config disable` - Disable bot responses
- `/sync` - Sync commands to server (NEW)
- `/sync all:true` - Sync commands to all servers (NEW)

## Natural Language Features

The bot now understands natural language commands:

### Action Commands
```
give @alexei 20 gold pieces
give @alexei a sword
set @alexei level to 10
```

### State Queries
```
how much gold do I have?
how much gold does @alexei have?
what is my inventory?
```

### Questions
```
@bot_name what is the project status?
@bot_name explain the document
```

## Command Sync

### Automatic Sync
Commands sync automatically:
- On bot startup (after 2 seconds)
- When bot joins a new guild
- Commands sync to all guilds the bot is in

### Manual Sync
If commands don't appear, use:
```
/sync
```

Or sync to all servers:
```
/sync all:true
```

## Troubleshooting

### Commands Not Appearing

1. **Wait for startup**: Commands sync 2 seconds after bot starts
2. **Check logs**: Look for "Syncing commands to..." messages
3. **Manual sync**: Use `/sync` command
4. **Check permissions**: Bot needs "applications.commands" permission
5. **Check guild ID**: Ensure bot is in the server

### Enhanced Features Not Working

1. **Check RAG server**: Look for "Using Enhanced RAG Pipeline" in logs
2. **Verify imports**: Ensure `enhanced_rag_pipeline.py` exists
3. **Check dependencies**: All enhanced modules must be available

### Command Sync Errors

- **Rate limits**: Bot waits 1 second between guilds
- **Permissions**: Bot needs "Manage Server" or "Administrator" permission
- **Guild not found**: Bot must be in the server

## Integration Details

### RAG Server (`rag_server.py`)
- Uses `EnhancedRAGPipeline` by default
- Falls back to `RAGPipeline` if enhanced not available
- All queries go through enhanced pipeline with:
  - Intelligent memory retrieval
  - User context tracking
  - Action parsing
  - State management
  - Tool calling

### Discord Bot (`discord-bot/index.js`)
- Loads all commands from `src/commands/`
- Syncs commands on startup and guild join
- Passes `channel_id` to RAG service
- Supports all enhanced features

### RAG Service (`discord-bot/src/ragServicePersistent.js`)
- Communicates with `rag_server.py` via JSON-RPC
- Passes `channel_id` for channel-based memories
- Supports document filtering
- Handles timeouts and reconnection

## Next Steps

1. **Restart the bot** to load new commands
2. **Use `/sync`** if commands don't appear
3. **Test enhanced features** with action commands
4. **Check logs** for "Using Enhanced RAG Pipeline" message

## Notes

- Commands sync automatically but may take a few seconds
- Enhanced features require all Python dependencies
- Channel-based memories improve context for multi-user channels
- Action commands work naturally: "give @user 20 gold"

