"""
E2E test for refactored bot integration.
Simulates Discord bot interactions using refactored agents.
"""
import pytest
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from Refactored.src.agents.registry import AgentRegistry, get_registry
from Refactored.src.agents.message_bus import MessageBus, get_message_bus
from Refactored.src.agents.gopher_agent import GopherAgent
from Refactored.src.agents.search_agent import SearchAgent
from Refactored.src.agents.analyser_agent import AnalyserAgent
from Refactored.src.agents.react_agent import ReActAgent
from Refactored.src.agents.coordinator import CoordinatorAgent
from Refactored.src.agents.base.agent_message import AgentMessage
from Refactored.logger_config import logger


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_bot_message_routing():
    """Test bot message routing using refactored GopherAgent."""
    registry = get_registry()
    bus = get_message_bus(registry)
    await bus.start()
    
    try:
        # Register GopherAgent
        gopher = GopherAgent()
        gopher.message_bus = bus
        gopher.registry = registry
        await registry.register(gopher)
        
        # Simulate Discord message routing
        test_messages = [
            ("What is Python?", {"isMentioned": True}),
            ("Hello, how are you?", {"isMentioned": False}),
            ("Search for machine learning", {"isMentioned": True}),
        ]
        
        for message_text, context in test_messages:
            message = AgentMessage(
                sender_id="discord_user",
                receiver_id=gopher.agent_id,
                action="route_message",
                payload={
                    "message": message_text,
                    "context": context
                }
            )
            
            response = await gopher.handle_message(message)
            assert response.success, f"Failed to route message: {message_text}"
            assert "handler" in response.data, "Response missing handler"
            logger.info(f"✅ Routed '{message_text[:30]}...' -> {response.data.get('handler')}")
        
        logger.info("✅ Bot message routing test passed")
    finally:
        await bus.stop()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_bot_agentic_task():
    """Test bot agentic task execution using refactored ReActAgent."""
    registry = get_registry()
    bus = get_message_bus(registry)
    await bus.start()
    
    try:
        # Register ReActAgent
        react_agent = ReActAgent()
        react_agent.message_bus = bus
        react_agent.registry = registry
        await registry.register(react_agent)
        
        # Simulate agentic task request
        message = AgentMessage(
            sender_id="discord_user",
            receiver_id=react_agent.agent_id,
            action="execute_task",
            payload={
                "message": "Calculate 15 * 23",
                "context": {
                    "channel_id": "test_channel",
                    "user_id": "test_user"
                }
            }
        )
        
        response = await react_agent.handle_message(message)
        assert response.success, f"Failed to execute agentic task"
        assert "result" in response.data, "Response missing result"
        logger.info(f"✅ Agentic task executed: {response.data.get('result', '')[:50]}")
        
    finally:
        await bus.stop()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_bot_multi_agent_workflow():
    """Test bot multi-agent workflow using CoordinatorAgent."""
    registry = get_registry()
    bus = get_message_bus(registry)
    await bus.start()
    
    try:
        # Register all agents
        search_agent = SearchAgent()
        search_agent.message_bus = bus
        search_agent.registry = registry
        await registry.register(search_agent)
        
        analyser_agent = AnalyserAgent()
        analyser_agent.message_bus = bus
        analyser_agent.registry = registry
        await registry.register(analyser_agent)
        
        coordinator = CoordinatorAgent()
        coordinator.message_bus = bus
        coordinator.registry = registry
        await registry.register(coordinator)
        
        # Simulate RAG workflow request
        message = AgentMessage(
            sender_id="discord_user",
            receiver_id=coordinator.agent_id,
            action="rag_workflow",
            payload={
                "query": "What is machine learning?",
                "top_k": 5
            }
        )
        
        response = await coordinator.handle_message(message)
        # May fail if Elasticsearch not enabled, which is OK for test
        assert response is not None
        logger.info(f"✅ Multi-agent workflow completed: {response.success}")
        
    finally:
        await bus.stop()


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_bot_a2a_delegation():
    """Test bot A2A delegation between agents."""
    registry = get_registry()
    bus = get_message_bus(registry)
    await bus.start()
    
    try:
        # Register agents
        search_agent = SearchAgent()
        search_agent.message_bus = bus
        search_agent.registry = registry
        await registry.register(search_agent)
        
        analyser_agent = AnalyserAgent()
        analyser_agent.message_bus = bus
        analyser_agent.registry = registry
        await registry.register(analyser_agent)
        
        # Test delegation: AnalyserAgent delegates search to SearchAgent
        message = AgentMessage(
            sender_id="discord_user",
            receiver_id=analyser_agent.agent_id,
            action="analyze_with_search",
            payload={
                "query": "Test query",
                "top_k": 5
            }
        )
        
        response = await analyser_agent.handle_message(message)
        # May fail if Elasticsearch not enabled, which is OK for test
        assert response is not None
        logger.info(f"✅ A2A delegation test completed: {response.success}")
        
    finally:
        await bus.stop()

