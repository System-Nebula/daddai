"""
HTTP server wrapper for Refactored Agent Server using FastAPI.
Provides REST API endpoints for Discord bot integration.
"""
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("ERROR: FastAPI and pydantic are required. Install with: pip install fastapi uvicorn pydantic")
    sys.exit(1)

from Refactored.src.api.refactored_agent_server import get_server
from Refactored.logger_config import logger

# Initialize FastAPI app
app = FastAPI(title="Refactored Agent HTTP Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get server instance (singleton)
server_instance = get_server()


# Request/Response models
class RouteMessageRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class RunAgenticTaskRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class ShouldUseAgenticModeRequest(BaseModel):
    message: str
    intent_result: Optional[Dict[str, Any]] = None


class AcceptTradeRequest(BaseModel):
    trade_id: str
    accepting_user_id: str


class DeclineTradeRequest(BaseModel):
    trade_id: str
    declining_user_id: str


# Startup event - initialize server
@app.on_event("startup")
async def startup_event():
    """Initialize the refactored agent server on startup."""
    try:
        await server_instance.initialize()
        logger.info("✅ Refactored Agent Server initialized")
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}", exc_info=True)
        raise


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        await server_instance.close()
        logger.info("Refactored Agent Server closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


# Routes
@app.post("/route_message")
async def route_message(request: RouteMessageRequest):
    """Route a message to determine the appropriate handler."""
    try:
        if not request.message:
            raise HTTPException(status_code=400, detail="message is required")
        
        result = await server_instance.route_message(
            request.message,
            request.context or {}
        )
        return result
    except Exception as e:
        logger.error(f"Error in route_message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run_agentic_task")
async def run_agentic_task(request: RunAgenticTaskRequest):
    """Run an agentic task using the ReAct agent."""
    try:
        if not request.message:
            raise HTTPException(status_code=400, detail="message is required")
        
        logger.info(f"Received agentic task request: {request.message[:100]}...")
        logger.debug(f"Context: {request.context}")
        
        result = await server_instance.run_agentic_task(
            request.message,
            request.context or {}
        )
        
        logger.info(f"Agentic task completed. Status: {result.get('status', 'unknown')}")
        logger.debug(f"Result preview: {str(result.get('result', ''))[:200]}...")
        
        return result
    except Exception as e:
        logger.error(f"Error in run_agentic_task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/should_use_agentic_mode")
async def should_use_agentic_mode(request: ShouldUseAgenticModeRequest):
    """Check if agentic mode should be used."""
    try:
        if not request.message:
            raise HTTPException(status_code=400, detail="message is required")
        
        result = await server_instance.should_use_agentic_mode(
            request.message,
            request.intent_result
        )
        return {"should_use": result}
    except Exception as e:
        logger.error(f"Error in should_use_agentic_mode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "refactored_agent_server",
        "initialized": server_instance._initialized
    }


@app.get("/ping")
async def ping():
    """Ping endpoint."""
    return {"status": "ok"}


@app.get("/get_trade")
async def get_trade(trade_id: str):
    """Get trade data by trade_id."""
    try:
        from Refactored.src.tools.trade_tool import TradeTool
        trade_tool = TradeTool()
        trade_data = trade_tool.get_trade(trade_id)
        if not trade_data:
            raise HTTPException(status_code=404, detail="Trade not found")
        return trade_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trade: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/accept_trade")
async def accept_trade(request: AcceptTradeRequest):
    """Accept a trade offer."""
    try:
        from Refactored.src.tools.trade_tool import TradeTool
        trade_tool = TradeTool()
        result = trade_tool.accept_trade(request.trade_id, request.accepting_user_id)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to accept trade"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting trade: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/decline_trade")
async def decline_trade(request: DeclineTradeRequest):
    """Decline a trade offer."""
    try:
        from Refactored.src.tools.trade_tool import TradeTool
        trade_tool = TradeTool()
        result = trade_tool.decline_trade(request.trade_id, request.declining_user_id)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to decline trade"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error declining trade: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update_campaign_thread")
async def update_campaign_thread(campaign_id: str, thread_id: str):
    """Update campaign with Discord thread ID."""
    try:
        from Refactored.src.tools.dnd_campaign_tool import DnDCampaignTool
        campaign_tool = DnDCampaignTool()
        result = await campaign_tool.update_campaign_state(
            campaign_id,
            {"thread_id": thread_id},
            "Thread ID updated"
        )
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to update thread"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating campaign thread: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get_campaign_by_thread")
async def get_campaign_by_thread(thread_id: str):
    """Get campaign data by Discord thread ID."""
    try:
        from Refactored.src.tools.dnd_campaign_tool import DnDCampaignTool
        campaign_tool = DnDCampaignTool()
        
        # Search for campaign with this thread_id
        with campaign_tool.driver.session() as session:
            result = session.run("""
                MATCH (c:Campaign)
                WHERE c.campaign_data CONTAINS $thread_id
                RETURN c.campaign_data AS campaign_data
                LIMIT 1
            """,
                thread_id=thread_id
            )
            
            record = result.single()
            if not record:
                raise HTTPException(status_code=404, detail="Campaign not found for this thread")
            
            import json
            campaign_data = json.loads(record["campaign_data"]) if isinstance(record["campaign_data"], str) else record["campaign_data"]
            return campaign_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign by thread: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host='localhost', port=8766):
    """Run the HTTP server using uvicorn."""
    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn is required. Install with: pip install uvicorn")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("🚀 Refactored Agent HTTP Server")
    logger.info("=" * 60)
    logger.info(f"Starting on http://{host}:{port}")
    logger.info("Endpoints:")
    logger.info("  POST /route_message - Route a message")
    logger.info("  POST /run_agentic_task - Run an agentic task")
    logger.info("  POST /should_use_agentic_mode - Check if agentic mode should be used")
    logger.info("  GET /health - Health check")
    logger.info("  GET /ping - Ping endpoint")
    logger.info("=" * 60)
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Refactored Agent HTTP Server')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8766, help='Port to bind to')
    
    args = parser.parse_args()
    run_server(args.host, args.port)

