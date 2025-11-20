"""
Unit tests for BaseAgent.
"""
import pytest
import asyncio
from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_message import AgentMessage, AgentResponse, MessageType
from Refactored.src.agents.base.agent_capability import AgentCapability, CapabilityType


class MockTestAgent(BaseAgent):
    """Test agent implementation."""
    
    def __init__(self, agent_id: str = "mock_agent", name: str = "MockTestAgent"):
        super().__init__(agent_id=agent_id, name=name, description="Mock agent for testing")
    
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        return AgentResponse.success_response(data={"processed": True})


@pytest.mark.asyncio
async def test_base_agent_initialization():
    """Test BaseAgent initialization."""
    agent = MockTestAgent(agent_id="test_agent", name="TestAgent")
    assert agent.agent_id == "test_agent"
    assert agent.name == "TestAgent"
    assert agent.capabilities is not None


@pytest.mark.asyncio
async def test_register_capability():
    """Test capability registration."""
    agent = MockTestAgent(agent_id="test_agent")
    capability = AgentCapability(
        capability_type=CapabilityType.SEARCH,
        description="Test capability"
    )
    agent.register_capability(capability)
    assert agent.capabilities.has(CapabilityType.SEARCH)


@pytest.mark.asyncio
async def test_register_message_handler():
    """Test message handler registration."""
    agent = MockTestAgent(agent_id="test_agent")
    
    async def handler(message: AgentMessage):
        return AgentResponse.success_response(data={"handled": True})
    
    agent.register_message_handler("test_action", handler)
    assert "test_action" in agent._message_handlers


@pytest.mark.asyncio
async def test_process_message():
    """Test message processing."""
    agent = MockTestAgent(agent_id="test_agent")
    message = AgentMessage(
        sender_id="sender",
        receiver_id="test_agent",
        action="test_action",
        payload={}
    )
    
    response = await agent.handle_message(message)
    assert response.success
    assert response.data["processed"] is True


@pytest.mark.asyncio
async def test_get_stats():
    """Test getting agent statistics."""
    agent = MockTestAgent(agent_id="test_agent")
    stats = agent.get_stats()
    assert stats["agent_id"] == "test_agent"
    assert "messages_sent" in stats
    assert "messages_received" in stats

