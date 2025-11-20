"""
Integration tests for A2A communication patterns.
"""
import pytest
import asyncio
from Refactored.src.agents.registry import AgentRegistry
from Refactored.src.agents.message_bus import MessageBus
from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_message import AgentMessage, AgentResponse
from Refactored.src.agents.base.agent_capability import AgentCapability, CapabilityType


class MockSearchAgent(BaseAgent):
    """Mock search agent for testing."""
    
    def __init__(self, agent_id: str = "search_agent"):
        super().__init__(agent_id=agent_id, name="MockSearchAgent", description="Mock search agent")
    
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        return AgentResponse.success_response(data={
            "results": [{"text": "Test result", "file_name": "test.txt"}],
            "count": 1
        })


class MockAnalyserAgent(BaseAgent):
    """Mock analyser agent for testing."""
    
    def __init__(self, agent_id: str = "analyser_agent"):
        super().__init__(agent_id=agent_id, name="MockAnalyserAgent", description="Mock analyser agent")
    
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        return AgentResponse.success_response(data={
            "analysis": "Test analysis",
            "confidence": 0.9
        })


@pytest.mark.asyncio
async def test_agent_to_agent_communication():
    """Test direct agent-to-agent communication."""
    registry = AgentRegistry()
    bus = MessageBus(registry)
    await bus.start()
    
    try:
        # Register agents
        search_agent = MockSearchAgent(agent_id="search_agent")
        search_agent.register_capability(AgentCapability(
            capability_type=CapabilityType.SEARCH,
            description="Test search"
        ))
        search_agent.message_bus = bus
        search_agent.registry = registry
        
        await registry.register(search_agent)
        
        # Create sender agent
        sender = MockAnalyserAgent(agent_id="analyser_agent")
        sender.message_bus = bus
        sender.registry = registry
        await registry.register(sender)
        
        # Send message
        response = await sender.send_message(
            receiver_id="search_agent",
            action="search",
            payload={"query": "test"}
        )
        
        assert response is not None
        assert response.success
        # Response data may be nested, check both levels
        data = response.data
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        assert "results" in data
    finally:
        await bus.stop()


@pytest.mark.asyncio
async def test_agent_delegation():
    """Test agent delegation via capability lookup."""
    registry = AgentRegistry()
    bus = MessageBus(registry)
    await bus.start()
    
    try:
        # Register search agent
        search_agent = MockSearchAgent(agent_id="search_agent")
        search_agent.register_capability(AgentCapability(
            capability_type=CapabilityType.SEARCH,
            description="Test search"
        ))
        search_agent.message_bus = bus
        search_agent.registry = registry
        await registry.register(search_agent)
        
        # Create delegating agent
        delegator = MockAnalyserAgent(agent_id="delegator")
        delegator.message_bus = bus
        delegator.registry = registry
        await registry.register(delegator)
        
        # Delegate task
        response = await delegator.delegate_to_agent(
            capability_type=CapabilityType.SEARCH,
            action="search",
            payload={"query": "test"}
        )
        
        assert response is not None
        assert response.success
    finally:
        await bus.stop()

