# Refactored RAG HTTP Server

HTTP server for the refactored RAG system using FastAPI. Integrates refactored agent architecture with EnhancedRAGPipeline for full feature support.

## Features

- ✅ Uses refactored agent architecture (SearchAgent, CoordinatorAgent)
- ✅ Full EnhancedRAGPipeline feature support (memory, tools, hybrid search, etc.)
- ✅ HTTP/JSON-RPC compatible interface
- ✅ FastAPI async support
- ✅ Health check endpoints

## Installation

Install required dependencies:

```bash
pip install -r Refactored/requirements_http_server.txt
```

Or install individually:

```bash
pip install fastapi uvicorn pydantic
```

## Usage

### Start the server

```bash
# From project root
python -m Refactored.src.api.refactored_rag_http_server --host localhost --port 8767

# Or use the startup script
python -m Refactored.scripts.start_refactored_rag_server
```

### Environment Variables

- `REFACTORED_RAG_HOST` - Host to bind to (default: localhost)
- `REFACTORED_RAG_PORT` - Port to bind to (default: 8767)

## API Endpoints

### POST /query

Query the RAG system.

**Request:**
```json
{
  "question": "What is Python?",
  "top_k": 10,
  "temperature": 0.7,
  "max_tokens": 600,
  "user_id": "user123",
  "channel_id": "channel123",
  "use_memory": true,
  "use_hybrid_search": true
}
```

**Response:**
```json
{
  "answer": "...",
  "context_chunks": 5,
  "memories_used": 2,
  "question": "What is Python?",
  "source_documents": [...],
  "source_memories": [...],
  "timing": {...},
  "is_casual_conversation": false,
  "service_routing": "rag",
  "tool_calls": []
}
```

### POST /query_jsonrpc

Query using JSON-RPC format (for compatibility with old client).

**Request:**
```json
{
  "id": 1,
  "method": "query",
  "params": {
    "question": "What is Python?",
    "top_k": 10
  }
}
```

**Response:**
```json
{
  "id": 1,
  "result": {
    "answer": "...",
    "context_chunks": 5,
    ...
  },
  "error": null
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "refactored_rag_server",
  "initialized": true
}
```

### GET /ping

Simple ping endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

## Architecture

```
Discord Bot (TypeScript)
    ↓ HTTP
Refactored RAG HTTP Server (FastAPI)
    ↓
EnhancedRAGPipeline (Full Features)
    ↓
Refactored Agent Architecture
    - SearchAgent (Hybrid Search)
    - CoordinatorAgent (Workflow)
    - MessageBus (A2A Communication)
```

## Integration with Discord Bot

The refactored Discord bot uses `refactoredRagService.ts` which connects to this HTTP server instead of the old stdin/stdout RAG server.

Set environment variables in the Discord bot:
- `REFACTORED_RAG_HOST` - RAG server host (default: localhost)
- `REFACTORED_RAG_PORT` - RAG server port (default: 8767)
- `REFACTORED_RAG_TIMEOUT` - Request timeout in ms (default: 120000)

## Benefits

1. **Unified Architecture**: Both agent routing and RAG queries use the refactored agent architecture
2. **Better Performance**: HTTP is more efficient than stdin/stdout for persistent connections
3. **Full Feature Support**: All EnhancedRAGPipeline features available
4. **Scalability**: Can run multiple instances behind a load balancer
5. **Observability**: Standard HTTP endpoints for monitoring

