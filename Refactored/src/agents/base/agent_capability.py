"""
Agent capability definitions for dynamic agent discovery.
"""
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class CapabilityType(Enum):
    """Types of agent capabilities."""
    SEARCH = "search"
    ANALYSIS = "analysis"
    REFLECTION = "reflection"
    REASONING = "reasoning"
    ROUTING = "routing"
    MEMORY = "memory"
    TOOL_EXECUTION = "tool_execution"
    VALIDATION = "validation"
    COORDINATION = "coordination"
    CODE_EXECUTION = "code_execution"
    IMAGE_GENERATION = "image_generation"
    VISION = "vision"
    DOCUMENT_PROCESSING = "document_processing"


@dataclass
class AgentCapability:
    """
    Represents an agent's capability.
    
    Attributes:
        capability_type: Type of capability
        description: Human-readable description
        parameters: Expected parameters for this capability
        returns: Expected return type/format
        metadata: Additional capability metadata
    """
    capability_type: CapabilityType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    returns: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert capability to dictionary."""
        return {
            "capability_type": self.capability_type.value,
            "description": self.description,
            "parameters": self.parameters,
            "returns": self.returns,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCapability":
        """Create capability from dictionary."""
        return cls(
            capability_type=CapabilityType(data["capability_type"]),
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            returns=data.get("returns"),
            metadata=data.get("metadata", {})
        )


@dataclass
class CapabilitySet:
    """
    Set of capabilities for an agent.
    
    Attributes:
        capabilities: List of agent capabilities
    """
    capabilities: List[AgentCapability] = field(default_factory=list)
    
    def add(self, capability: AgentCapability):
        """Add a capability."""
        self.capabilities.append(capability)
    
    def has(self, capability_type: CapabilityType) -> bool:
        """Check if agent has a specific capability."""
        return any(cap.capability_type == capability_type for cap in self.capabilities)
    
    def get(self, capability_type: CapabilityType) -> Optional[AgentCapability]:
        """Get a specific capability."""
        for cap in self.capabilities:
            if cap.capability_type == capability_type:
                return cap
        return None
    
    def get_types(self) -> Set[CapabilityType]:
        """Get all capability types."""
        return {cap.capability_type for cap in self.capabilities}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert capability set to dictionary."""
        return {
            "capabilities": [cap.to_dict() for cap in self.capabilities]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilitySet":
        """Create capability set from dictionary."""
        return cls(
            capabilities=[AgentCapability.from_dict(cap) for cap in data.get("capabilities", [])]
        )

