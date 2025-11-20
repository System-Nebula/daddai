# Refactored Agent HTTP Server

HTTP server wrapper for the Refactored Agent Server using FastAPI.

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
python -m Refactored.src.api.refactored_agent_http_server --host localhost --port 8766

# Or use the startup script
python -m Refactored.scripts.start_refactored_agent_server
```

### Environment Variables

- `REFACTORED_AGENT_HOST` - Host to bind to (default: localhost)
- `REFACTORED_AGENT_PORT` - Port to bind to (default: 8766)

## API Endpoints

### POST /route_message
Route a message to determine the appropriate handler.

**Request:**
```json
{
  "message": "What is Python?",
  "context": {
    "isMentioned": true,
    "userId": "user123"
  }
}
```

**Response:**
```json
{
  "handler": "rag",
  "intent": {
    "intent": "question",
    "should_respond": true,
    "needs_rag": true,
    "needs_tools": false
  },
  "routing_confidence": 0.8
}
```

### POST /run_agentic_task
Run an agentic task using the ReAct agent.

**Request:**
```json
{
  "message": "Calculate 15 * 23",
  "context": {
    "channelId": "channel123",
    "userId": "user123"
  }
}
```

**Response:**
```json
{
  "status": "success",
  "result": "345",
  "tool_calls": [...],
  "steps": [...]
}
```

### POST /should_use_agentic_mode
Check if agentic mode should be used.

**Request:**
```json
{
  "message": "Calculate 15 * 23",
  "intent_result": null
}
```

**Response:**
```json
{
  "should_use": true
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "refactored_agent_server",
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

## Troubleshooting

### Import Errors
If you get import errors for FastAPI or uvicorn, make sure they're installed:
```bash
pip install fastapi uvicorn pydantic
```

### Port Already in Use
Change the port:
```bash
python -m Refactored.src.api.refactored_agent_http_server --port 9000
```

### Async Errors
The server uses FastAPI which properly handles async operations. If you see async-related errors, ensure you're using the latest version of FastAPI and uvicorn.

