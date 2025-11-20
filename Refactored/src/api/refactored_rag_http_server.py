"""
Refactored RAG HTTP Server using FastAPI.
Integrates refactored agent architecture with EnhancedRAGPipeline for full feature support.
"""
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("ERROR: FastAPI and pydantic are required. Install with: pip install fastapi uvicorn pydantic")
    sys.exit(1)

try:
    from src.core.enhanced_rag_pipeline import EnhancedRAGPipeline
except ImportError:
    # Try alternative import path
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.core.enhanced_rag_pipeline import EnhancedRAGPipeline
from Refactored.src.agents.registry import AgentRegistry, get_registry
from Refactored.src.agents.message_bus import MessageBus, get_message_bus
from Refactored.src.agents.search_agent import SearchAgent
from Refactored.logger_config import logger

# Initialize FastAPI app
app = FastAPI(title="Refactored RAG HTTP Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
rag_pipeline: Optional[EnhancedRAGPipeline] = None
search_agent: Optional[SearchAgent] = None
registry: Optional[AgentRegistry] = None
bus: Optional[MessageBus] = None
_initialized = False


# Request/Response models
class RAGQueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 10
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 600
    max_context_tokens: Optional[int] = 1500
    user_id: Optional[str] = None
    channel_id: Optional[str] = None
    use_memory: Optional[bool] = True
    use_shared_docs: Optional[bool] = True
    use_hybrid_search: Optional[bool] = True
    use_query_expansion: Optional[bool] = True
    use_temporal_weighting: Optional[bool] = True
    doc_id: Optional[str] = None
    doc_filename: Optional[str] = None
    username: Optional[str] = None
    mentioned_user_id: Optional[str] = None
    is_admin: Optional[bool] = False


class RAGQueryResponse(BaseModel):
    answer: str
    context_chunks: int
    memories_used: int
    question: str
    source_documents: list
    source_memories: list
    timing: Dict[str, Any]
    is_casual_conversation: bool
    service_routing: str
    tool_calls: list


# Startup event - initialize server
@app.on_event("startup")
async def startup_event():
    """Initialize the refactored RAG server on startup."""
    global rag_pipeline, search_agent, registry, bus, _initialized
    
    if _initialized:
        return
    
    try:
        logger.info("Initializing Refactored RAG HTTP Server...")
        
        # Initialize refactored agent architecture
        registry = get_registry()
        bus = get_message_bus(registry)
        await bus.start()
        
        # Initialize SearchAgent for refactored architecture
        search_agent = SearchAgent()
        search_agent.message_bus = bus
        search_agent.registry = registry
        await registry.register(search_agent)
        
        # Initialize EnhancedRAGPipeline (has all features)
        logger.info("Loading EnhancedRAGPipeline...")
        rag_pipeline = EnhancedRAGPipeline()
        
        _initialized = True
        logger.info("✅ Refactored RAG HTTP Server initialized")
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}", exc_info=True)
        raise


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global bus, _initialized
    try:
        if bus:
            await bus.stop()
        _initialized = False
        logger.info("Refactored RAG HTTP Server closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


# Routes
@app.post("/query", response_model=Dict[str, Any])
async def query_rag(request: RAGQueryRequest):
    """Query the RAG system."""
    global rag_pipeline
    
    if not _initialized or not rag_pipeline:
        raise HTTPException(status_code=503, detail="Server not initialized")
    
    try:
        if not request.question:
            raise HTTPException(status_code=400, detail="question is required")
        
        # Use EnhancedRAGPipeline for full feature support
        # It's async, so we need to await it
        result = await rag_pipeline.query(
            question=request.question,
            top_k=request.top_k or 10,
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens or 600,
            max_context_tokens=request.max_context_tokens or 1500,
            user_id=request.user_id,
            channel_id=request.channel_id,
            use_memory=request.use_memory if request.use_memory is not None else True,
            use_shared_docs=request.use_shared_docs if request.use_shared_docs is not None else True,
            use_hybrid_search=request.use_hybrid_search if request.use_hybrid_search is not None else True,
            use_query_expansion=request.use_query_expansion if request.use_query_expansion is not None else True,
            use_temporal_weighting=request.use_temporal_weighting if request.use_temporal_weighting is not None else True,
            doc_id=request.doc_id,
            doc_filename=request.doc_filename,
            username=request.username,
            mentioned_user_id=request.mentioned_user_id,
            is_admin=request.is_admin if request.is_admin is not None else False
        )
        
        # Format response to match old RAG server format
        return {
            "answer": result.get("answer", ""),
            "context_chunks": len(result.get("context_chunks", [])),
            "memories_used": len(result.get("source_memories", [])),
            "question": result.get("question", request.question),
            "source_documents": result.get("source_documents", []),
            "source_memories": result.get("source_memories", []),
            "timing": result.get("timing", {}),
            "is_casual_conversation": result.get("is_casual_conversation", False),
            "service_routing": result.get("service_routing", "rag"),
            "tool_calls": result.get("tool_calls", [])
        }
    except Exception as e:
        logger.error(f"Error in query_rag: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query_jsonrpc")
async def query_rag_jsonrpc(request: Dict[str, Any]):
    """Query the RAG system using JSON-RPC format (for compatibility with old client)."""
    global rag_pipeline
    
    if not _initialized or not rag_pipeline:
        return {
            "id": request.get("id", 0),
            "result": None,
            "error": "Server not initialized"
        }
    
    try:
        request_id = request.get("id", 0)
        method = request.get("method")
        params = request.get("params", {})
        
        if method != "query":
            return {
                "id": request_id,
                "result": None,
                "error": f"Unknown method: {method}"
            }
        
        # Extract parameters
        question = params.get("question", "")
        if not question:
            return {
                "id": request_id,
                "result": None,
                "error": "question parameter is required"
            }
        
        # Use EnhancedRAGPipeline
        result = await rag_pipeline.query(
            question=question,
            top_k=params.get("top_k", 10),
            temperature=params.get("temperature", 0.7),
            max_tokens=params.get("max_tokens", 600),
            max_context_tokens=params.get("max_context_tokens", 1500),
            user_id=params.get("user_id"),
            channel_id=params.get("channel_id") or params.get("user_id"),
            use_memory=params.get("use_memory", True) and not params.get("doc_id") and not params.get("doc_filename"),
            use_shared_docs=params.get("use_shared_docs", True),
            use_hybrid_search=params.get("use_hybrid_search", True),
            use_query_expansion=params.get("use_query_expansion", True),
            use_temporal_weighting=params.get("use_temporal_weighting", True),
            doc_id=params.get("doc_id"),
            doc_filename=params.get("doc_filename"),
            mentioned_user_id=params.get("mentioned_user_id"),
            is_admin=params.get("is_admin", False)
        )
        
        # Format response
        response = {
            "answer": result.get("answer", ""),
            "context_chunks": len(result.get("context_chunks", [])),
            "memories_used": len(result.get("source_memories", [])),
            "question": result.get("question", question),
            "source_documents": result.get("source_documents", []),
            "source_memories": result.get("source_memories", []),
            "timing": result.get("timing", {}),
            "is_casual_conversation": result.get("is_casual_conversation", False),
            "service_routing": result.get("service_routing", "rag"),
            "tool_calls": result.get("tool_calls", [])
        }
        
        return {
            "id": request_id,
            "result": response,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error in query_rag_jsonrpc: {e}", exc_info=True)
        return {
            "id": request.get("id", 0),
            "result": None,
            "error": str(e)
        }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "refactored_rag_server",
        "initialized": _initialized
    }


@app.get("/ping")
async def ping():
    """Ping endpoint."""
    return {"status": "ok"}


def run_server(host='localhost', port=8767):
    """Run the HTTP server using uvicorn."""
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn is required. Install with: pip install uvicorn")
        sys.exit(1)
    
    logger.info(f"Starting Refactored RAG HTTP Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Refactored RAG HTTP Server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8767, help="Port to bind to")
    args = parser.parse_args()
    
    run_server(host=args.host, port=args.port)

