"""
Pytest configuration and fixtures for refactored tests.
"""
import pytest
import asyncio
from typing import Dict, Any

from Refactored.src.agents.registry import AgentRegistry, get_registry
from Refactored.src.agents.message_bus import MessageBus, get_message_bus
from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_message import AgentMessage, MessageType


@pytest.fixture
def registry():
    """Create a fresh agent registry for each test."""
    return AgentRegistry()


@pytest.fixture
async def message_bus(registry):
    """Create a message bus with registry."""
    bus = MessageBus(registry)
    await bus.start()
    yield bus
    await bus.stop()


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    class MockAgent(BaseAgent):
        def __init__(self, agent_id: str = "mock_agent"):
            super().__init__(agent_id=agent_id, name="MockAgent", description="Mock agent for testing")
            self.received_messages = []
        
        async def process_message(self, message: AgentMessage):
            self.received_messages.append(message)
            return {"success": True, "data": {"processed": True}}
    
    return MockAgent()


@pytest.fixture
def sample_message():
    """Create a sample agent message."""
    return AgentMessage(
        sender_id="test_sender",
        receiver_id="test_receiver",
        action="test_action",
        payload={"test": "data"}
    )


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

