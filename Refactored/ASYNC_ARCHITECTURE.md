# Async Architecture - Refactored Code

## Overview

The refactored codebase is designed to be **fully async and non-blocking** to maximize performance and concurrency.

## Architecture

### ✅ Fully Async Components

1. **HTTP Servers** (FastAPI)
   - All endpoints are `async def`
   - FastAPI handles async request/response automatically
   - No blocking I/O operations

2. **Agent-to-Agent (A2A) Communication**
   - `MessageBus` - Fully async with worker threads
   - `AgentRegistry` - Async registration with locks
   - All agent message handlers are `async def`
   - Request/response uses `asyncio.Future` and `asyncio.wait_for`

3. **RAG Pipeline**
   - `RAGPipeline.query()` - Fully async
   - Uses async agent delegation via `CoordinatorAgent`
   - All agent interactions are async

4. **Search Agent**
   - `_handle_search()` - Async handler
   - Blocking operations (embedding generation, Elasticsearch I/O) run in `ThreadPoolExecutor`
   - Non-blocking for the event loop

### ⚠️ Blocking Operations (Handled Properly)

Some operations are inherently blocking but are handled to avoid blocking the event loop:

1. **Embedding Generation** (CPU/GPU computation)
   - Runs in `ThreadPoolExecutor` via `run_in_executor()`
   - Non-blocking for async event loop

2. **Elasticsearch I/O** (Network I/O)
   - Runs in `ThreadPoolExecutor` via `run_in_executor()`
   - Non-blocking for async event loop

3. **Image Generation Tool** (LangChain tool - sync by design)
   - Runs async `generate_image()` in `ThreadPoolExecutor`
   - Uses `asyncio.run()` in thread to avoid blocking
   - Timeout protection (5 minutes)

## Flow Diagram

```
HTTP Request (FastAPI)
    ↓ async
Agent Handler (async def)
    ↓ async
MessageBus (async queue)
    ↓ async
Agent Processing (async def)
    ↓ async (or executor for blocking ops)
Tool Execution / Search / RAG
    ↓ async
Response (async)
```

## Key Design Principles

1. **All HTTP endpoints are async** - FastAPI handles concurrency
2. **All agent handlers are async** - Non-blocking message processing
3. **Blocking operations use executors** - CPU-bound or sync I/O runs in threads
4. **Message bus uses async queues** - `asyncio.Queue` for non-blocking message passing
5. **Worker threads for message processing** - Multiple workers handle messages concurrently

## Performance Benefits

- ✅ **Concurrent request handling** - Multiple requests processed simultaneously
- ✅ **Non-blocking I/O** - Network operations don't block other requests
- ✅ **Efficient resource usage** - Event loop handles many concurrent operations
- ✅ **Scalability** - Can handle high request volumes without blocking

## Verification

All async operations are properly awaited:
- ✅ `await` used for all async calls
- ✅ `asyncio.run_in_executor()` for blocking operations
- ✅ No `time.sleep()` or blocking `.join()` calls
- ✅ FastAPI async endpoints properly defined

The refactored code is **fully async and non-blocking**! 🚀

