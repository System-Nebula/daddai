"""
Refactored Agent Server for Discord bot integration.
Provides HTTP/JSON-RPC interface compatible with Discord bot expectations.
"""
import json
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from Refactored.src.agents.registry import AgentRegistry, get_registry
from Refactored.src.agents.message_bus import MessageBus, get_message_bus
from Refactored.src.agents.gopher_agent import GopherAgent
from Refactored.src.agents.react_agent import ReActAgent
from Refactored.src.agents.base.agent_message import AgentMessage
from Refactored.logger_config import logger


class RefactoredAgentServer:
    """
    Server that exposes refactored agents via JSON-RPC for Discord bot integration.
    """
    
    def __init__(self):
        """Initialize the server."""
        self.registry = get_registry()
        self.bus = get_message_bus(self.registry)
        self.gopher_agent: Optional[GopherAgent] = None
        self.react_agent: Optional[ReActAgent] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize agents and message bus."""
        if self._initialized:
            return
        
        await self.bus.start()
        
        # Register GopherAgent
        self.gopher_agent = GopherAgent()
        self.gopher_agent.message_bus = self.bus
        self.gopher_agent.registry = self.registry
        await self.registry.register(self.gopher_agent)
        
        # Register ReActAgent
        self.react_agent = ReActAgent()
        self.react_agent.message_bus = self.bus
        self.react_agent.registry = self.registry
        await self.registry.register(self.react_agent)
        
        self._initialized = True
        logger.info("✅ Refactored Agent Server initialized")
    
    async def route_message(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Route a message (compatible with Discord bot interface).
        
        Args:
            message: User message
            context: Context dictionary
            
        Returns:
            Routing result dictionary
        """
        await self.initialize()
        
        agent_message = AgentMessage(
            sender_id=context.get("userId", "unknown") if context else "unknown",
            receiver_id=self.gopher_agent.agent_id,
            action="route_message",
            payload={
                "message": message,
                "context": context or {}
            }
        )
        
        response = await self.gopher_agent.handle_message(agent_message)
        
        if response.success:
            routing_data = response.data
            return {
                "handler": routing_data.get("handler", "chat"),
                "intent": {
                    "intent": routing_data.get("intent", "conversation"),
                    "should_respond": routing_data.get("should_respond", True),
                    "needs_rag": routing_data.get("intent") in ["question", "search"],
                    "needs_tools": False
                },
                "routing_confidence": routing_data.get("confidence", 0.8)
            }
        else:
            # Fallback routing
            return {
                "handler": "chat",
                "intent": {
                    "intent": "conversation",
                    "should_respond": True,
                    "needs_rag": False,
                    "needs_tools": False
                },
                "routing_confidence": 0.5,
                "fallback": True
            }
    
    async def run_agentic_task(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run an agentic task (compatible with Discord bot interface).
        
        Args:
            message: Task message
            context: Context dictionary
            
        Returns:
            Task result dictionary
        """
        from Refactored.logger_config import logger
        
        logger.info(f"run_agentic_task called with message: {message[:100]}...")
        await self.initialize()
        
        agent_message = AgentMessage(
            sender_id=context.get("userId", "unknown") if context else "unknown",
            receiver_id=self.react_agent.agent_id,
            action="execute_task",
            payload={
                "message": message,
                "context": context or {}
            }
        )
        
        logger.debug(f"Sending message to ReActAgent: {agent_message.action}")
        response = await self.react_agent.handle_message(agent_message)
        logger.debug(f"Received response from ReActAgent. Success: {response.success}")
        
        if response.success:
            result_data = response.data
            result_str = result_data.get("result", "")
            tool_calls = result_data.get("tool_calls", [])
            logger.info(f"Task completed successfully. Result length: {len(str(result_str))}")
            logger.info(f"Returning {len(tool_calls)} tool calls")
            
            # Log tool call details for debugging
            for i, tc in enumerate(tool_calls):
                tool_name = tc.get("tool", "unknown") if isinstance(tc, dict) else "not_dict"
                has_result = "result" in tc if isinstance(tc, dict) else False
                if has_result and isinstance(tc.get("result"), dict):
                    result_keys = list(tc["result"].keys())
                    has_base64 = "image_base64" in tc["result"]
                    logger.info(f"Tool call {i}: tool={tool_name}, has_result={has_result}, result_keys={result_keys}, has_image_base64={has_base64}")
                else:
                    logger.info(f"Tool call {i}: tool={tool_name}, has_result={has_result}, result_type={type(tc.get('result')) if isinstance(tc, dict) else 'N/A'}")
            
            return {
                "status": "success",
                "result": result_str,
                "tool_calls": tool_calls,
                "steps": result_data.get("steps", [])
            }
        else:
            logger.error(f"Task failed: {response.error}")
            return {
                "status": "error",
                "error": response.error or "Unknown error",
                "result": None
            }
    
    async def should_use_agentic_mode(self, message: str, intent_result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determine if agentic mode should be used.
        
        Args:
            message: User message
            intent_result: Optional intent classification result
            
        Returns:
            True if agentic mode should be used
        """
        # Simple heuristic: use agentic mode for complex tasks
        complex_keywords = ["calculate", "compute", "solve", "analyze", "generate", "create"]
        return any(keyword in message.lower() for keyword in complex_keywords)
    
    async def close(self):
        """Close the server and stop agents."""
        await self.bus.stop()
        logger.info("Refactored Agent Server closed")


# Global server instance
_server: Optional[RefactoredAgentServer] = None


def get_server() -> RefactoredAgentServer:
    """Get the global server instance."""
    global _server
    if _server is None:
        _server = RefactoredAgentServer()
    return _server


async def main():
    """Main entry point for testing."""
    server = get_server()
    
    try:
        await server.initialize()
        
        # Test routing
        print("Testing message routing...")
        routing = await server.route_message("What is Python?", {"isMentioned": True})
        print(f"Routing result: {json.dumps(routing, indent=2)}")
        
        # Test agentic task
        print("\nTesting agentic task...")
        result = await server.run_agentic_task("Calculate 15 * 23", {"channel_id": "test"})
        print(f"Agentic result: {json.dumps(result, indent=2)}")
        
    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(main())

