# Refactored Agent System & Discord Bot

This repository contains the refactored agent architecture system and the Discord bot that uses it.

## Overview

- **Refactored/**: Python-based agent system with Smart Agent-to-Agent (A2A) communication
- **discord-bot-refactored/**: TypeScript Discord bot that communicates with the refactored agent system

## Prerequisites

### For Refactored Agent System
- Python 3.8 or higher
- pip (Python package manager)
- Neo4j database (optional, for graph storage)
- LLM provider access (OpenAI, Chutes AI, or LMStudio)

### For Discord Bot
- Node.js 18.0 or higher
- npm (Node package manager)
- Discord Bot Token

## Quick Start

### 1. Set Up Refactored Agent System

```bash
# Navigate to Refactored directory
cd Refactored

# Install Python dependencies
pip install -r requirements_http_server.txt

# Create environment file (optional, uses defaults if not set)
# Copy and configure .env with your settings:
# - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD (if using Neo4j)
# - LLM_PROVIDER (chutes, openai, or lmstudio)
# - API keys for your chosen LLM provider
```

### 2. Set Up Discord Bot

```bash
# Navigate to discord-bot-refactored directory
cd discord-bot-refactored

# Install Node.js dependencies
npm install

# Create environment file
cp .env.example .env

# Edit .env and set:
# - DISCORD_TOKEN=your_discord_bot_token
# - REFACTORED_AGENT_HOST=localhost (default)
# - REFACTORED_AGENT_PORT=8766 (default)
```

### 3. Start the Services

#### Terminal 1: Start Refactored Agent Server

```bash
cd Refactored
python -m src.api.refactored_agent_http_server --host localhost --port 8766
```

Or use the convenience script:

```bash
cd Refactored
python scripts/start_refactored_agent_server.py
```

#### Terminal 2: Start Discord Bot

```bash
cd discord-bot-refactored
npm start
```

For development with auto-reload:

```bash
npm run dev
```

## Configuration

### Refactored Agent System Configuration

The main configuration is in `Refactored/config.py`. You can override settings via environment variables:

**Neo4j Configuration:**
- `NEO4J_URI`: Neo4j connection URI (default: `bolt://localhost:7687`)
- `NEO4J_USER`: Neo4j username (default: `neo4j`)
- `NEO4J_PASSWORD`: Neo4j password

**LLM Provider Configuration:**
- `LLM_PROVIDER`: Choose `chutes`, `openai`, or `lmstudio`
- For Chutes AI: Set `CHUTES_API_KEY` and optionally `CHUTES_BASE_URL`
- For OpenAI: Set `OPENAI_API_KEY` and optionally `OPENAI_BASE_URL`
- For LMStudio: Set `LMSTUDIO_BASE_URL` (default: `http://localhost:1234/v1`)

**Embedding Configuration:**
- `EMBEDDING_MODEL`: Embedding model to use (default: `BAAI/bge-base-en-v1.5`)

### Discord Bot Configuration

Environment variables in `discord-bot-refactored/.env`:

- `DISCORD_TOKEN`: Your Discord bot token (required)
- `REFACTORED_AGENT_HOST`: Host of the refactored agent server (default: `localhost`)
- `REFACTORED_AGENT_PORT`: Port of the refactored agent server (default: `8766`)
- `REFACTORED_AGENT_TIMEOUT`: Request timeout in milliseconds (default: `30000`)
- `REFACTORED_AGENT_HTTPS`: Use HTTPS for agent server (default: `false`)

## Architecture

### Refactored Agent System

The refactored system implements Smart Agent-to-Agent (A2A) communication:

- **BaseAgent**: Abstract base class for all agents
- **AgentRegistry**: Dynamic agent discovery and registration
- **MessageBus**: Async message routing and event handling
- **AgentMessage**: Standardized message protocol

**Available Agents:**
- **SearchAgent**: Performs hybrid search operations
- **AnalyserAgent**: Generates analysis and delegates search
- **ReflectionAgent**: Evaluates quality and communicates with other agents
- **ReActAgent**: Implements ReAct pattern with agent delegation
- **GopherAgent**: Router agent coordinating multiple agents
- **CoordinatorAgent**: Orchestrates multi-agent workflows

### Discord Bot

The Discord bot communicates with the refactored agent system via HTTP:

- Receives Discord messages and commands
- Forwards requests to the refactored agent server
- Handles responses and displays them in Discord
- Supports slash commands and message-based interactions

## Testing

### Test Refactored Agent System

```bash
cd Refactored
pytest tests/
```

### Test Discord Bot Integration

```bash
cd discord-bot-refactored
npm run typecheck  # Type checking
```

## Project Structure

```
.
├── Refactored/                    # Python agent system
│   ├── src/
│   │   ├── agents/               # Agent implementations
│   │   ├── api/                  # HTTP server implementations
│   │   ├── core/                 # Core RAG pipeline
│   │   └── tools/                # Agent tools
│   ├── scripts/                  # Startup scripts
│   ├── tests/                    # Test suite
│   ├── config.py                 # Configuration
│   └── requirements_http_server.txt
│
└── discord-bot-refactored/        # TypeScript Discord bot
    ├── src/
    │   ├── commands/             # Discord slash commands
    │   ├── chatService.ts        # Chat service
    │   ├── refactoredAgentClient.ts  # Agent client
    │   └── webServer.ts          # Web server
    ├── index.ts                  # Main entry point
    ├── package.json
    └── tsconfig.json
```

## Troubleshooting

### Refactored Agent Server Won't Start

1. Check that Python dependencies are installed: `pip install -r requirements_http_server.txt`
2. Verify your LLM provider configuration in `Refactored/config.py` or environment variables
3. Check that the port (default 8766) is not already in use

### Discord Bot Can't Connect to Agent Server

1. Ensure the refactored agent server is running
2. Verify `REFACTORED_AGENT_HOST` and `REFACTORED_AGENT_PORT` in `.env` match the server
3. Check network connectivity between bot and server

### Agent Server Returns Errors

1. Verify your LLM provider API keys are set correctly
2. Check Neo4j connection if using graph storage
3. Review server logs for detailed error messages

## Additional Documentation

- **Refactored System**: See `Refactored/README.md` for detailed architecture documentation
- **Discord Bot**: See `discord-bot-refactored/README.md` for bot-specific documentation
- **HTTP Server**: See `Refactored/README_HTTP_SERVER.md` for server API documentation
- **RAG Server**: See `Refactored/README_REFACTORED_RAG_SERVER.md` for RAG-specific docs

## License

MIT
