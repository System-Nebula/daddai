#!/usr/bin/env python3
"""
GopherAgent HTTP API - FastAPI server for GopherAgent

Exposes:
  POST /classify_intent
  POST /route_message
  POST /batch_classify  (optional)
  GET  /get_metrics

Designed to be used by your Node.js wrapper with GOPHER_AGENT_HTTP=true.
"""

import os
import asyncio
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from src.agents.gopher_agent import get_gopher_agent
from logger_config import logger

# --------------------------------------------------------------------
# Pydantic models
# --------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    use_cache: bool = True


class RouteRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    intent_result: Optional[Dict[str, Any]] = None


class BatchItem(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class BatchClassifyRequest(BaseModel):
    messages: List[BatchItem]


class MetricsResponse(BaseModel):
    intent_classifications: int
    cache_hits: int
    cache_misses: int
    avg_latency_ms: float
    gpu_inference_count: int
    cache_hit_rate: float
    gpu_enabled: bool
    cache_size: int


# --------------------------------------------------------------------
# FastAPI app
# --------------------------------------------------------------------

app = FastAPI(title="GopherAgent HTTP API", version="1.0.0")

# Singleton GopherAgent instance (shared across requests)
agent = get_gopher_agent()


# --------------------------------------------------------------------
# Helper to run sync agent methods in a thread pool (non-blocking)
# --------------------------------------------------------------------

async def _run_in_executor(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: func(*args, **kwargs),
    )


# --------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------

@app.post("/classify_intent")
async def classify_intent(req: ClassifyRequest):
    """
    Classify message intent using GopherAgent.
    This wraps the synchronous classify_intent in a thread executor
    so the FastAPI event loop stays responsive.
    """
    context = req.context or {}
    result = await _run_in_executor(
        agent.classify_intent,
        req.message,
        context,
        req.use_cache,
    )
    return result


@app.post("/route_message")
async def route_message(req: RouteRequest):
    """
    Route message based on intent. If intent_result is not provided,
    classify_intent will be called first (with cache).
    """
    context = req.context or {}
    intent_result = req.intent_result

    if intent_result is None:
        intent_result = await _run_in_executor(
            agent.classify_intent,
            req.message,
            context,
            True,  # use_cache
        )

    result = await _run_in_executor(
        agent.route_message,
        req.message,
        context,
        intent_result,
    )
    return result


@app.post("/batch_classify")
async def batch_classify(req: BatchClassifyRequest):
    """
    Batch classify multiple messages.
    """
    message_tuples = [(item.message, item.context or {}) for item in req.messages]
    results = await _run_in_executor(
        agent.batch_classify,
        message_tuples,
    )
    return {"results": results}


@app.get("/get_metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Get GopherAgent performance metrics.
    """
    metrics = agent.get_metrics()
    return metrics


# --------------------------------------------------------------------
# Uvicorn entrypoint
# --------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("GOPHER_AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("GOPHER_AGENT_PORT", "8765"))

    logger.info(f"Starting GopherAgent HTTP server on {host}:{port}")
    uvicorn.run(
        "src.agents.gopher_agent_api:app",
        host=host,
        port=port,
        reload=False,
        workers=1,  # one process; we already use threads inside
    )
