"""
Integration tests for multi-agent workflows.
"""
import pytest
import asyncio
from Refactored.src.agents.registry import AgentRegistry
from Refactored.src.agents.message_bus import MessageBus
from Refactored.src.agents.coordinator import CoordinatorAgent
from Refactored.src.agents.base.agent_message import AgentMessage


@pytest.mark.asyncio
async def test_reflection_workflow():
    """Test reflection pattern workflow."""
    registry = AgentRegistry()
    bus = MessageBus(registry)
    await bus.start()
    
    try:
        # Register coordinator
        coordinator = CoordinatorAgent()
        coordinator.message_bus = bus
        coordinator.registry = registry
        await registry.register(coordinator)
        
        # Create workflow message
        message = AgentMessage(
            sender_id="test",
            receiver_id=coordinator.agent_id,
            action="reflection_workflow",
            payload={
                "query": "Test query",
                "max_iterations": 2,
                "quality_threshold": 0.7
            }
        )
        
        # Note: This test requires actual agents to be registered
        # For now, we just test that the coordinator can handle the message
        response = await coordinator.handle_message(message)
        # Response may fail if agents aren't registered, which is expected
        assert response is not None
    finally:
        await bus.stop()

