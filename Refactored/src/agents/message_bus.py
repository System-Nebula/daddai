"""
Message Bus for async agent-to-agent communication and event routing.
"""
from typing import Dict, List, Optional, Callable, Set, TYPE_CHECKING
import asyncio
from collections import defaultdict
from datetime import datetime

from Refactored.src.agents.base.agent_message import (
    AgentMessage, AgentResponse, MessageType, MessagePriority
)
from Refactored.src.agents.registry import AgentRegistry
from Refactored.logger_config import logger
from Refactored.config import A2A_MESSAGE_TIMEOUT, A2A_MAX_RETRIES

if TYPE_CHECKING:
    from Refactored.src.agents.base.base_agent import BaseAgent


class MessageBus:
    """
    Central message bus for agent communication.
    
    Features:
    - Async message routing
    - Request/response handling with timeouts
    - Event publishing/subscription
    - Message queuing and priority handling
    """
    
    def __init__(self, registry: AgentRegistry):
        """
        Initialize message bus.
        
        Args:
            registry: Agent registry for routing messages
        """
        self.registry = registry
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._event_subscribers: Dict[str, Set[str]] = defaultdict(set)  # event_type -> agent_ids
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._priority_queues: Dict[MessagePriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in MessagePriority
        }
        self._is_running = False
        self._worker_tasks: List[asyncio.Task] = []
        self._stats = {
            "messages_routed": 0,
            "events_published": 0,
            "requests_handled": 0,
            "timeouts": 0,
            "errors": 0
        }
    
    async def start(self, num_workers: int = 3):
        """
        Start the message bus workers.
        
        Args:
            num_workers: Number of worker tasks to process messages
        """
        if self._is_running:
            logger.warning("Message bus already running")
            return
        
        self._is_running = True
        
        # Start worker tasks
        for i in range(num_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._worker_tasks.append(task)
        
        logger.info(f"Message bus started with {num_workers} workers")
    
    async def stop(self):
        """Stop the message bus."""
        self._is_running = False
        
        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        # Cancel pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        
        self._pending_requests.clear()
        logger.info("Message bus stopped")
    
    async def send_message(self, message: AgentMessage):
        """
        Send a message (fire and forget).
        
        Args:
            message: Message to send
        """
        if message.receiver_id:
            # Direct message
            await self._route_message(message)
        else:
            # Event message
            await self.publish_event(message)
    
    async def send_request(
        self,
        message: AgentMessage,
        timeout: Optional[float] = None
    ) -> AgentResponse:
        """
        Send a request and wait for response.
        
        Args:
            message: Request message
            timeout: Timeout in seconds (uses message timeout if None)
            
        Returns:
            AgentResponse
        """
        if message.message_type != MessageType.REQUEST:
            raise ValueError("send_request requires a REQUEST message")
        
        timeout = timeout or message.timeout
        
        # Create future for response
        future = asyncio.Future()
        self._pending_requests[message.message_id] = future
        
        try:
            # Route the message
            await self._route_message(message)
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                self._stats["requests_handled"] += 1
                return response
            except asyncio.TimeoutError:
                self._stats["timeouts"] += 1
                logger.warning(f"Request {message.message_id} timed out after {timeout}s")
                return AgentResponse.error_response(
                    f"Request timed out after {timeout} seconds",
                    error_code="TIMEOUT"
                )
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error sending request: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
        finally:
            # Clean up
            self._pending_requests.pop(message.message_id, None)
    
    async def publish_event(self, message: AgentMessage):
        """
        Publish an event to all subscribed agents.
        
        Args:
            message: Event message
        """
        if message.message_type != MessageType.EVENT:
            message.message_type = MessageType.EVENT
        
        event_type = message.action
        subscriber_ids = self._event_subscribers.get(event_type, set())
        
        if not subscriber_ids:
            logger.debug(f"No subscribers for event: {event_type}")
            return
        
        self._stats["events_published"] += 1
        
        # Send to all subscribers
        tasks = []
        for agent_id in subscriber_ids:
            agent = self.registry.get_agent(agent_id)
            if agent and self.registry.is_healthy(agent_id):
                event_message = AgentMessage(
                    message_id=message.message_id,
                    message_type=MessageType.EVENT,
                    sender_id=message.sender_id,
                    receiver_id=agent_id,
                    action=event_type,
                    payload=message.payload,
                    metadata=message.metadata
                )
                tasks.append(self._deliver_message(agent, event_message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"Published event {event_type} to {len(tasks)} subscribers")
    
    def subscribe_to_event(self, agent_id: str, event_type: str):
        """
        Subscribe an agent to an event type.
        
        Args:
            agent_id: Agent ID
            event_type: Event type to subscribe to
        """
        self._event_subscribers[event_type].add(agent_id)
        logger.debug(f"Agent {agent_id} subscribed to event: {event_type}")
    
    def unsubscribe_from_event(self, agent_id: str, event_type: str):
        """
        Unsubscribe an agent from an event type.
        
        Args:
            agent_id: Agent ID
            event_type: Event type to unsubscribe from
        """
        self._event_subscribers[event_type].discard(agent_id)
        logger.debug(f"Agent {agent_id} unsubscribed from event: {event_type}")
    
    async def _route_message(self, message: AgentMessage):
        """
        Route a message to its destination.
        
        Args:
            message: Message to route
        """
        if not message.receiver_id:
            logger.warning(f"Message {message.message_id} has no receiver_id")
            return
        
        agent = self.registry.get_agent(message.receiver_id)
        if not agent:
            logger.warning(f"Agent {message.receiver_id} not found")
            if message.message_type == MessageType.REQUEST:
                # Send error response
                await self._handle_response(message.create_error_response(
                    f"Agent {message.receiver_id} not found",
                    error_code="AGENT_NOT_FOUND"
                ))
            return
        
        if not self.registry.is_healthy(message.receiver_id):
            logger.warning(f"Agent {message.receiver_id} is not healthy")
            if message.message_type == MessageType.REQUEST:
                await self._handle_response(message.create_error_response(
                    f"Agent {message.receiver_id} is not healthy",
                    error_code="AGENT_UNHEALTHY"
                ))
            return
        
        self._stats["messages_routed"] += 1
        
        # Deliver message
        await self._deliver_message(agent, message)
    
    async def _deliver_message(self, agent: "BaseAgent", message: AgentMessage):
        """
        Deliver a message to an agent.
        
        Args:
            agent: Target agent
            message: Message to deliver
        """
        try:
            if message.message_type == MessageType.REQUEST:
                # Handle request/response
                response = await agent.handle_message(message)
                await self._handle_response(message.create_response(response.to_dict(), success=response.success))
            elif message.message_type == MessageType.EVENT:
                # Handle event
                await agent.handle_event(message)
            else:
                # Other message types
                await agent.handle_message(message)
        except Exception as e:
            logger.error(f"Error delivering message to {agent.agent_id}: {e}", exc_info=True)
            if message.message_type == MessageType.REQUEST:
                await self._handle_response(message.create_error_response(str(e)))
    
    async def _handle_response(self, response_message: AgentMessage):
        """
        Handle a response message.
        
        Args:
            response_message: Response message
        """
        correlation_id = response_message.correlation_id
        if correlation_id and correlation_id in self._pending_requests:
            future = self._pending_requests[correlation_id]
            if not future.done():
                # Extract response from message
                response_data = response_message.payload
                if response_message.message_type == MessageType.ERROR:
                    response = AgentResponse.error_response(
                        response_data.get("error", "Unknown error"),
                        error_code=response_data.get("error_code")
                    )
                else:
                    response = AgentResponse.success_response(data=response_data)
                
                future.set_result(response)
    
    async def _worker(self, worker_id: str):
        """Worker task to process messages."""
        logger.debug(f"Message bus worker {worker_id} started")
        
        while self._is_running:
            try:
                # Process priority queues in order
                message = None
                for priority in [MessagePriority.URGENT, MessagePriority.HIGH, MessagePriority.NORMAL, MessagePriority.LOW]:
                    try:
                        message = self._priority_queues[priority].get_nowait()
                        break
                    except asyncio.QueueEmpty:
                        continue
                
                if message is None:
                    # No messages, wait a bit
                    await asyncio.sleep(0.1)
                    continue
                
                # Process message
                await self._route_message(message)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message bus worker {worker_id}: {e}", exc_info=True)
                self._stats["errors"] += 1
        
        logger.debug(f"Message bus worker {worker_id} stopped")
    
    def get_stats(self) -> Dict[str, any]:
        """Get message bus statistics."""
        return {
            **self._stats,
            "is_running": self._is_running,
            "pending_requests": len(self._pending_requests),
            "event_subscribers": {
                event_type: len(agent_ids)
                for event_type, agent_ids in self._event_subscribers.items()
            }
        }


# Global message bus instance
_message_bus: Optional[MessageBus] = None


def get_message_bus(registry: Optional[AgentRegistry] = None) -> MessageBus:
    """Get the global message bus instance."""
    global _message_bus
    if _message_bus is None:
        if registry is None:
            from Refactored.src.agents.registry import get_registry
            registry = get_registry()
        _message_bus = MessageBus(registry)
    return _message_bus

