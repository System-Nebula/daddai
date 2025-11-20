"""
Refactored agents with Smart A2A communication.
"""
from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_message import AgentMessage, AgentResponse
from Refactored.src.agents.base.agent_capability import AgentCapability, CapabilityType
from Refactored.src.agents.registry import AgentRegistry, get_registry
from Refactored.src.agents.message_bus import MessageBus, get_message_bus
from Refactored.src.agents.search_agent import SearchAgent
from Refactored.src.agents.analyser_agent import AnalyserAgent
from Refactored.src.agents.reflection_agent import ReflectionAgent
from Refactored.src.agents.react_agent import ReActAgent
from Refactored.src.agents.gopher_agent import GopherAgent
from Refactored.src.agents.coordinator import CoordinatorAgent

__all__ = [
    "BaseAgent",
    "AgentMessage",
    "AgentResponse",
    "AgentCapability",
    "CapabilityType",
    "AgentRegistry",
    "get_registry",
    "MessageBus",
    "get_message_bus",
    "SearchAgent",
    "AnalyserAgent",
    "ReflectionAgent",
    "ReActAgent",
    "GopherAgent",
    "CoordinatorAgent"
]
