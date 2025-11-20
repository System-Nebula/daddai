# Auto-Start Refactored Servers

The refactored Discord bot now automatically starts both the A2A (Agent-to-Agent) server and the RAG server when it starts.

## How It Works

When you run `npm start` in the `discord-bot-refactored` directory, the bot will:

1. **Start Refactored Agent Server (A2A)** on port 8766 (default)
   - Handles message routing and agentic tasks
   - Uses the refactored agent architecture

2. **Start Refactored RAG Server** on port 8767 (default)
   - Handles document queries and RAG operations
   - Uses EnhancedRAGPipeline with refactored agent architecture

3. **Monitor Server Health**
   - Periodically checks if servers are healthy
   - Automatically restarts servers if they crash
   - Logs server status

4. **Clean Shutdown**
   - Stops both servers gracefully when the bot shuts down

## Configuration

### Environment Variables

You can configure the servers using environment variables in your `.env` file:

```bash
# Agent Server (A2A)
REFACTORED_AGENT_HOST=localhost
REFACTORED_AGENT_PORT=8766

# RAG Server
REFACTORED_RAG_HOST=localhost
REFACTORED_RAG_PORT=8767

# Python path (if not in PATH)
PYTHON_PATH=python
```

### Manual Server Control

If you want to run servers manually instead of auto-start:

1. Set environment variable to disable auto-start (not implemented yet, servers will auto-start)
2. Or start servers manually before starting the bot - the bot will detect they're already running

## Server Status

The bot logs server status:
- `✅ Refactored Agent Server (A2A) is ready!` - Agent server started
- `✅ Refactored RAG Server is ready!` - RAG server started
- `⚠️  [Server Name] health check failed` - Server health check failed (will attempt restart)

## Troubleshooting

### Servers Won't Start

1. **Check Python Installation**
   ```bash
   python --version
   # Should be Python 3.8+
   ```

2. **Check Dependencies**
   ```bash
   pip install fastapi uvicorn pydantic
   ```

3. **Check Ports**
   ```bash
   # Check if ports are already in use
   netstat -ano | findstr ":8766"
   netstat -ano | findstr ":8767"
   ```

4. **Check Logs**
   - Server startup logs appear in the console
   - Look for error messages from Python processes

### Servers Already Running

If servers are already running externally, the bot will detect them and skip starting new instances. You'll see:
```
✅ Refactored Agent Server (A2A) is already running
✅ Refactored RAG Server is already running
```

### Server Crashes

If a server crashes, the bot will:
1. Detect the crash via health check
2. Log a warning
3. Attempt to restart the server automatically

## Architecture

```
Discord Bot (TypeScript)
    ├─> RefactoredServerManager
    │   ├─> Starts Agent Server (Python)
    │   └─> Starts RAG Server (Python)
    │
    ├─> Refactored Agent Client
    │   └─> Connects to Agent Server (port 8766)
    │
    └─> Refactored RAG Client
        └─> Connects to RAG Server (port 8767)
```

## Benefits

1. **Simplified Deployment**: No need to manually start servers
2. **Automatic Recovery**: Servers restart if they crash
3. **Health Monitoring**: Continuous health checks
4. **Graceful Shutdown**: Clean shutdown of all processes

