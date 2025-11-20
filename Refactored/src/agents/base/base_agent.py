"""
Base agent class with Smart A2A communication capabilities.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
import asyncio
import time
from datetime import datetime

from Refactored.src.agents.base.agent_message import (
    AgentMessage, AgentResponse, MessageType, MessagePriority
)
from Refactored.src.agents.base.agent_capability import (
    AgentCapability, CapabilitySet, CapabilityType
)
from Refactored.logger_config import logger


class BaseAgent(ABC):
    """
    Abstract base class for all agents with Smart A2A communication.
    
    All agents should inherit from this class to enable:
    - Direct agent-to-agent communication
    - Capability registration and discovery
    - Message handling and routing
    - Event publishing and subscription
    """
    
    def __init__(self, agent_id: str, name: str, description: str = ""):
        """
        Initialize base agent.
        
        Args:
            agent_id: Unique identifier for this agent
            name: Human-readable agent name
            description: Agent description
        """
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.capabilities = CapabilitySet()
        self.message_bus = None  # Will be set by registry
        self.registry = None  # Will be set by registry
        self._message_handlers: Dict[str, Callable] = {}
        self._event_subscriptions: Dict[str, List[Callable]] = {}
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._is_running = False
        self._stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "requests_handled": 0,
            "errors": 0
        }
    
    def register_capability(self, capability: AgentCapability):
        """Register a capability this agent provides."""
        self.capabilities.add(capability)
        logger.debug(f"Agent {self.agent_id} registered capability: {capability.capability_type.value}")
    
    def register_message_handler(self, action: str, handler: Callable):
        """
        Register a handler for a specific action/message type.
        
        Args:
            action: Action name to handle
            handler: Callable that takes (message: AgentMessage) -> AgentResponse
        """
        self._message_handlers[action] = handler
        logger.debug(f"Agent {self.agent_id} registered handler for action: {action}")
    
    def subscribe_to_event(self, event_type: str, handler: Callable):
        """
        Subscribe to an event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Callable that takes (message: AgentMessage)
        """
        if event_type not in self._event_subscriptions:
            self._event_subscriptions[event_type] = []
        self._event_subscriptions[event_type].append(handler)
        logger.debug(f"Agent {self.agent_id} subscribed to event: {event_type}")
    
    async def send_message(
        self,
        receiver_id: str,
        action: str,
        payload: Dict[str, Any],
        timeout: float = 30.0,
        priority: MessagePriority = MessagePriority.NORMAL,
        wait_for_response: bool = True
    ) -> Optional[AgentResponse]:
        """
        Send a message to another agent.
        
        Args:
            receiver_id: ID of target agent
            action: Action to invoke
            payload: Message payload
            timeout: Timeout in seconds
            priority: Message priority
            wait_for_response: Whether to wait for response
            
        Returns:
            AgentResponse if wait_for_response=True, None otherwise
        """
        if not self.message_bus:
            raise RuntimeError("Message bus not initialized. Agent must be registered first.")
        
        message = AgentMessage(
            sender_id=self.agent_id,
            receiver_id=receiver_id,
            action=action,
            payload=payload,
            message_type=MessageType.REQUEST,
            timeout=timeout,
            priority=priority
        )
        
        self._stats["messages_sent"] += 1
        
        if wait_for_response:
            return await self.message_bus.send_request(message, timeout=timeout)
        else:
            await self.message_bus.send_message(message)
            return None
    
    async def send_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL
    ):
        """
        Publish an event to all subscribed agents.
        
        Args:
            event_type: Type of event
            payload: Event payload
            priority: Event priority
        """
        if not self.message_bus:
            raise RuntimeError("Message bus not initialized. Agent must be registered first.")
        
        message = AgentMessage(
            sender_id=self.agent_id,
            receiver_id=None,  # Events are broadcast
            action=event_type,
            payload=payload,
            message_type=MessageType.EVENT,
            priority=priority
        )
        
        await self.message_bus.publish_event(message)
        logger.debug(f"Agent {self.agent_id} published event: {event_type}")
    
    async def delegate_to_agent(
        self,
        capability_type: CapabilityType,
        action: str,
        payload: Dict[str, Any],
        timeout: float = 30.0
    ) -> Optional[AgentResponse]:
        """
        Delegate a task to an agent with a specific capability.
        
        Args:
            capability_type: Required capability type
            action: Action to invoke
            payload: Task payload
            timeout: Timeout in seconds
            
        Returns:
            AgentResponse from delegated agent
        """
        if not self.registry:
            raise RuntimeError("Agent registry not initialized. Agent must be registered first.")
        
        # Find agent with required capability
        agents = self.registry.find_agents_by_capability(capability_type)
        if not agents:
            return AgentResponse.error_response(
                f"No agent found with capability: {capability_type.value}"
            )
        
        # Use first available agent (could implement load balancing here)
        target_agent = agents[0]
        
        logger.info(f"Agent {self.agent_id} delegating {action} to {target_agent.agent_id}")
        return await self.send_message(
            receiver_id=target_agent.agent_id,
            action=action,
            payload=payload,
            timeout=timeout
        )
    
    async def handle_message(self, message: AgentMessage) -> AgentResponse:
        """
        Handle an incoming message.
        
        Args:
            message: Incoming message
            
        Returns:
            AgentResponse
        """
        self._stats["messages_received"] += 1
        
        try:
            # Check if we have a handler for this action
            handler = self._message_handlers.get(message.action)
            if handler:
                self._stats["requests_handled"] += 1
                start_time = time.time()
                response = await self._call_handler(handler, message)
                execution_time = time.time() - start_time
                response.execution_time = execution_time
                return response
            else:
                # Try abstract method
                response = await self.process_message(message)
                return response
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error handling message in agent {self.agent_id}: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
    
    async def _call_handler(self, handler: Callable, message: AgentMessage) -> AgentResponse:
        """Call a registered handler."""
        if asyncio.iscoroutinefunction(handler):
            result = await handler(message)
        else:
            result = handler(message)
        
        # Convert to AgentResponse if needed
        if isinstance(result, AgentResponse):
            return result
        elif isinstance(result, dict):
            return AgentResponse.success_response(data=result)
        else:
            return AgentResponse.success_response(data=result)
    
    async def handle_event(self, message: AgentMessage):
        """
        Handle an incoming event.
        
        Args:
            message: Event message
        """
        event_type = message.action
        handlers = self._event_subscriptions.get(event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)
    
    @abstractmethod
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        """
        Process a message. Subclasses must implement this.
        
        Args:
            message: Message to process
            
        Returns:
            AgentResponse
        """
        pass
    
    def start(self):
        """Start the agent."""
        self._is_running = True
        logger.info(f"Agent {self.agent_id} ({self.name}) started")
    
    def stop(self):
        """Stop the agent."""
        self._is_running = False
        logger.info(f"Agent {self.agent_id} ({self.name}) stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            **self._stats,
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": [cap.capability_type.value for cap in self.capabilities.capabilities],
            "is_running": self._is_running
        }
    
    def get_capabilities(self) -> CapabilitySet:
        """Get agent capabilities."""
        return self.capabilities

