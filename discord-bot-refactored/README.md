# Discord Bot - Refactored Architecture

This is a secondary Discord bot implementation that uses the refactored agent architecture with Smart Agent-to-Agent (A2A) communication.

## Features

- **Refactored Agent Integration**: Uses the refactored agent server for intelligent message routing
- **Agentic Task Execution**: Supports ReAct agent pattern for complex tasks
- **Simplified Architecture**: Cleaner, more maintainable codebase
- **HTTP-based Communication**: Communicates with refactored agent server via HTTP

## Prerequisites

- Node.js >= 18.0.0
- Python 3.8+ (for refactored agent server)
- Discord Bot Token

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment variables**:
   Copy `.env.example` to `.env` and fill in your values:
   ```bash
   cp .env.example .env
   ```

3. **Start the refactored agent server**:
   ```bash
   # From project root
   python -m Refactored.src.api.refactored_agent_http_server --host localhost --port 8766
   ```

4. **Start the Discord bot**:
   ```bash
   npm start
   # or for development with auto-reload
   npm run dev
   ```

## Environment Variables

- `DISCORD_TOKEN`: Your Discord bot token (required)
- `REFACTORED_AGENT_HOST`: Host of the refactored agent server (default: `localhost`)
- `REFACTORED_AGENT_PORT`: Port of the refactored agent server (default: `8766`)
- `REFACTORED_AGENT_TIMEOUT`: Request timeout in milliseconds (default: `30000`)
- `REFACTORED_AGENT_HTTPS`: Use HTTPS for agent server (default: `false`)
- `LOG_LEVEL`: Logging level (default: `info`)

## Architecture

### Components

1. **Refactored Agent Client** (`src/refactoredAgentClient.ts`):
   - HTTP client for communicating with the refactored agent server
   - Handles message routing, agentic tasks, and health checks

2. **Main Bot** (`index.ts`):
   - Discord bot implementation
   - Message handling and routing
   - Integration with refactored agent server

3. **Logger** (`src/logger.ts`):
   - Centralized logging with correlation IDs
   - Winston-based logging system

### Message Flow

1. User sends a message mentioning the bot
2. Bot extracts the question and builds context
3. Bot calls refactored agent server to route the message
4. Based on routing result:
   - **Agentic Mode**: Executes complex tasks using ReAct agent
   - **RAG Mode**: Handles question answering with RAG
   - **Chat Mode**: Simple conversational responses

## Differences from Original Bot

- **Simplified**: Removed complex features like document uploads, memory management, etc.
- **Refactored Backend**: Uses the new refactored agent server instead of legacy services
- **HTTP-based**: All communication with backend is via HTTP (no stdin/stdout)
- **Agentic-first**: Designed to leverage the refactored agent architecture

## Development

### Type Checking
```bash
npm run typecheck
```

### Building
```bash
npm run build
```

## Troubleshooting

### Bot doesn't respond
1. Check that the refactored agent server is running
2. Verify `REFACTORED_AGENT_HOST` and `REFACTORED_AGENT_PORT` are correct
3. Check bot logs for connection errors

### Agent server connection errors
1. Ensure the refactored agent server is started before the bot
2. Check firewall settings if using remote host
3. Verify the agent server is listening on the correct port

## License

MIT

