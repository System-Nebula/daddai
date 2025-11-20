"""
Unit tests for AgentRegistry.
"""
import pytest
import asyncio
from Refactored.src.agents.registry import AgentRegistry
from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_capability import AgentCapability, CapabilityType
from Refactored.src.agents.base.agent_message import AgentMessage, AgentResponse


class MockTestAgent(BaseAgent):
    def __init__(self, agent_id: str = "mock_agent"):
        super().__init__(agent_id=agent_id, name="MockTestAgent", description="Mock agent for testing")
    
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        return AgentResponse.success_response()


@pytest.mark.asyncio
async def test_register_agent():
    """Test agent registration."""
    registry = AgentRegistry()
    agent = MockTestAgent(agent_id="test_agent")
    agent.register_capability(AgentCapability(
        capability_type=CapabilityType.SEARCH,
        description="Test"
    ))
    
    await registry.register(agent)
    assert registry.get_agent("test_agent") == agent


@pytest.mark.asyncio
async def test_find_agents_by_capability():
    """Test finding agents by capability."""
    registry = AgentRegistry()
    agent = MockTestAgent(agent_id="test_agent")
    agent.register_capability(AgentCapability(
        capability_type=CapabilityType.SEARCH,
        description="Test"
    ))
    
    await registry.register(agent)
    agents = registry.find_agents_by_capability(CapabilityType.SEARCH)
    assert len(agents) == 1
    assert agents[0] == agent


@pytest.mark.asyncio
async def test_unregister_agent():
    """Test agent unregistration."""
    registry = AgentRegistry()
    agent = MockTestAgent(agent_id="test_agent")
    await registry.register(agent)
    
    await registry.unregister("test_agent")
    assert registry.get_agent("test_agent") is None


@pytest.mark.asyncio
async def test_get_stats():
    """Test getting registry statistics."""
    registry = AgentRegistry()
    agent = MockTestAgent(agent_id="test_agent")
    agent.register_capability(AgentCapability(
        capability_type=CapabilityType.SEARCH,
        description="Test"
    ))
    
    await registry.register(agent)
    stats = registry.get_stats()
    assert stats["total_agents"] == 1
    assert CapabilityType.SEARCH.value in stats["capabilities"]

