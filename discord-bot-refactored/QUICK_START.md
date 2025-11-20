# Quick Start Guide - Refactored Discord Bot

This guide will help you get the refactored Discord bot up and running quickly.

## Prerequisites

1. **Node.js** (>= 18.0.0)
2. **Python** (>= 3.8)
3. **Discord Bot Token** - Get one from [Discord Developer Portal](https://discord.com/developers/applications)

## Step 1: Install Dependencies

### Discord Bot
```bash
cd discord-bot-refactored
npm install
```

### Python Dependencies
Make sure you have the refactored code dependencies installed. From the project root:
```bash
pip install -r requirements.txt  # If you have one
# Or install individual packages as needed
```

## Step 2: Configure Environment

Create a `.env` file in `discord-bot-refactored/`:

```bash
DISCORD_TOKEN=your_discord_bot_token_here
REFACTORED_AGENT_HOST=localhost
REFACTORED_AGENT_PORT=8766
LOG_LEVEL=info
```

## Step 3: Start the Refactored Agent Server

In one terminal, start the refactored agent HTTP server:

```bash
# From project root
python -m Refactored.src.api.refactored_agent_http_server --host localhost --port 8766

# Or use the startup script
python -m Refactored.scripts.start_refactored_agent_server
```

You should see:
```
🚀 Refactored Agent HTTP Server starting on http://localhost:8766
Endpoints:
  POST /route_message - Route a message
  POST /run_agentic_task - Run an agentic task
  POST /should_use_agentic_mode - Check if agentic mode should be used
  GET /health - Health check
  GET /ping - Ping endpoint
```

## Step 4: Start the Discord Bot

In another terminal, start the Discord bot:

```bash
cd discord-bot-refactored
npm start
```

You should see:
```
✅ Refactored Discord Bot logged in as YourBot#1234
✅ Refactored Agent Server is healthy
```

## Step 5: Test the Bot

1. Invite your bot to a Discord server
2. Mention the bot in a channel: `@YourBot Hello!`
3. The bot should respond using the refactored agent architecture

## Troubleshooting

### Bot doesn't respond
- Check that the refactored agent server is running
- Verify the bot token is correct
- Check bot logs for errors

### Connection errors
- Ensure `REFACTORED_AGENT_HOST` and `REFACTORED_AGENT_PORT` match the server
- Check firewall settings
- Verify the agent server is accessible: `curl http://localhost:8766/health`

### Port already in use
- Change the port in `.env` and restart both services
- Or stop the service using that port

## Architecture Overview

```
Discord Bot (Node.js/TypeScript)
    ↓ HTTP
Refactored Agent Server (Python)
    ↓ A2A Communication
Refactored Agents (GopherAgent, ReActAgent, etc.)
```

The bot sends messages to the refactored agent server, which routes them through the agent architecture using A2A communication patterns.

## Next Steps

- Customize the bot's behavior in `index.ts`
- Add more handlers in the refactored agent server
- Extend the agent architecture with new agents

