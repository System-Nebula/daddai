"""
Refactored GopherAgent with Smart A2A communication.
Router agent that coordinates via A2A for intelligent message routing.
"""
from typing import Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_message import AgentMessage, AgentResponse
from Refactored.src.agents.base.agent_capability import AgentCapability, CapabilityType
from Refactored.logger_config import logger


class GopherAgent(BaseAgent):
    """
    Refactored GopherAgent with Smart A2A communication.
    Router agent that coordinates via A2A for intelligent message routing.
    """
    
    def __init__(self, agent_id: str = "gopher_agent"):
        """
        Initialize GopherAgent.
        
        Args:
            agent_id: Unique agent identifier
        """
        super().__init__(
            agent_id=agent_id,
            name="GopherAgent",
            description="Intelligent router agent for message routing and coordination"
        )
        
        # Register capabilities
        self.register_capability(AgentCapability(
            capability_type=CapabilityType.ROUTING,
            description="Route messages to appropriate handlers and coordinate workflows",
            parameters={
                "message": "str - User message",
                "context": "Dict - Context information"
            },
            returns="Dict with routing decision and handler"
        ))
        
        # Register message handlers
        self.register_message_handler("route_message", self._handle_route_message)
        self.register_message_handler("classify_intent", self._handle_classify_intent)
        
        logger.info(f"🤖 GopherAgent {agent_id} initialized with A2A support")
    
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        """
        Process incoming messages.
        
        Args:
            message: Incoming message
            
        Returns:
            AgentResponse
        """
        if message.action == "route_message":
            return await self._handle_route_message(message)
        elif message.action == "classify_intent":
            return await self._handle_classify_intent(message)
        else:
            return AgentResponse.error_response(
                f"Unknown action: {message.action}",
                error_code="UNKNOWN_ACTION"
            )
    
    async def _handle_route_message(self, message: AgentMessage) -> AgentResponse:
        """
        Handle route message request.
        
        Args:
            message: Route request message
            
        Returns:
            AgentResponse with routing decision
        """
        try:
            payload = message.payload
            user_message = payload.get("message", "")
            context = payload.get("context", {})
            
            if not user_message:
                return AgentResponse.error_response(
                    "Message parameter is required",
                    error_code="MISSING_MESSAGE"
                )
            
            # Simple routing logic (can be enhanced with LLM)
            routing = self.route_message(user_message, context)
            
            return AgentResponse.success_response(
                data=routing,
                metadata={"message": user_message[:100]}
            )
        except Exception as e:
            logger.error(f"Error in GopherAgent._handle_route_message: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
    
    async def _handle_classify_intent(self, message: AgentMessage) -> AgentResponse:
        """
        Handle intent classification request.
        
        Args:
            message: Intent classification request message
            
        Returns:
            AgentResponse with intent classification
        """
        try:
            payload = message.payload
            user_message = payload.get("message", "")
            context = payload.get("context", {})
            
            if not user_message:
                return AgentResponse.error_response(
                    "Message parameter is required",
                    error_code="MISSING_MESSAGE"
                )
            
            intent = self.classify_intent(user_message, context)
            
            return AgentResponse.success_response(
                data=intent,
                metadata={"message": user_message[:100]}
            )
        except Exception as e:
            logger.error(f"Error in GopherAgent._handle_classify_intent: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
    
    def route_message(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Route a message to appropriate handler.
        
        Args:
            message: User message
            context: Context information
            
        Returns:
            Routing decision dictionary
        """
        context = context or {}
        is_mentioned = context.get("isMentioned", False)
        has_question = "?" in message
        
        # Simple routing logic
        if is_mentioned or has_question:
            handler = "rag"
            intent = "question"
        elif any(word in message.lower() for word in ["search", "find", "look"]):
            handler = "rag"
            intent = "search"
        else:
            handler = "chat"
            intent = "conversation"
        
        return {
            "handler": handler,
            "intent": intent,
            "confidence": 0.8,
            "should_respond": True
        }
    
    def classify_intent(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Classify message intent.
        
        Args:
            message: User message
            context: Context information
            
        Returns:
            Intent classification dictionary
        """
        context = context or {}
        is_mentioned = context.get("isMentioned", False)
        has_question = "?" in message
        
        if is_mentioned or has_question:
            intent = "question"
            needs_rag = True
            needs_tools = False
        elif any(word in message.lower() for word in ["calculate", "compute", "solve"]):
            intent = "computation"
            needs_rag = False
            needs_tools = True
        else:
            intent = "conversation"
            needs_rag = False
            needs_tools = False
        
        return {
            "intent": intent,
            "should_respond": True,
            "needs_rag": needs_rag,
            "needs_tools": needs_tools
        }

