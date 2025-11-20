"""
Agent Registry for dynamic agent discovery and registration.
"""
from typing import Dict, List, Optional, Set
from collections import defaultdict
import asyncio
from datetime import datetime, timedelta

from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_capability import CapabilityType, AgentCapability
from Refactored.logger_config import logger


class AgentRegistry:
    """
    Registry for agent discovery and management.
    
    Features:
    - Dynamic agent registration/unregistration
    - Capability-based agent lookup
    - Agent health monitoring
    - Load balancing across multiple agents
    """
    
    def __init__(self):
        """Initialize the agent registry."""
        self._agents: Dict[str, BaseAgent] = {}
        self._capability_index: Dict[CapabilityType, List[BaseAgent]] = defaultdict(list)
        self._health_checks: Dict[str, datetime] = {}
        self._health_timeout = timedelta(seconds=60)  # Consider agent unhealthy after 60s
        self._lock = asyncio.Lock()
    
    async def register(self, agent: BaseAgent):
        """
        Register an agent in the registry.
        
        Args:
            agent: Agent to register
        """
        async with self._lock:
            if agent.agent_id in self._agents:
                logger.warning(f"Agent {agent.agent_id} already registered, updating...")
            
            self._agents[agent.agent_id] = agent
            
            # Index by capabilities
            for capability in agent.capabilities.capabilities:
                if agent not in self._capability_index[capability.capability_type]:
                    self._capability_index[capability.capability_type].append(agent)
            
            # Set registry reference in agent
            agent.registry = self
            
            # Update health check
            self._health_checks[agent.agent_id] = datetime.utcnow()
            
            logger.info(f"Registered agent: {agent.agent_id} ({agent.name}) with {len(agent.capabilities.capabilities)} capabilities")
    
    async def unregister(self, agent_id: str):
        """
        Unregister an agent from the registry.
        
        Args:
            agent_id: ID of agent to unregister
        """
        async with self._lock:
            if agent_id not in self._agents:
                logger.warning(f"Agent {agent_id} not found in registry")
                return
            
            agent = self._agents[agent_id]
            
            # Remove from capability index
            for capability in agent.capabilities.capabilities:
                if agent in self._capability_index[capability.capability_type]:
                    self._capability_index[capability.capability_type].remove(agent)
            
            # Remove agent
            del self._agents[agent_id]
            if agent_id in self._health_checks:
                del self._health_checks[agent_id]
            
            logger.info(f"Unregistered agent: {agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """
        Get an agent by ID.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent if found, None otherwise
        """
        return self._agents.get(agent_id)
    
    def find_agents_by_capability(
        self,
        capability_type: CapabilityType,
        healthy_only: bool = True
    ) -> List[BaseAgent]:
        """
        Find all agents with a specific capability.
        
        Args:
            capability_type: Required capability type
            healthy_only: Only return healthy agents
            
        Returns:
            List of agents with the capability
        """
        agents = self._capability_index.get(capability_type, [])
        
        if healthy_only:
            agents = [agent for agent in agents if self.is_healthy(agent.agent_id)]
        
        return agents
    
    def find_agent_by_capability(
        self,
        capability_type: CapabilityType,
        healthy_only: bool = True
    ) -> Optional[BaseAgent]:
        """
        Find a single agent with a specific capability.
        Uses round-robin for load balancing.
        
        Args:
            capability_type: Required capability type
            healthy_only: Only return healthy agents
            
        Returns:
            Agent if found, None otherwise
        """
        agents = self.find_agents_by_capability(capability_type, healthy_only)
        if agents:
            # Simple round-robin (could be improved with actual load balancing)
            return agents[0]
        return None
    
    def get_all_agents(self, healthy_only: bool = False) -> List[BaseAgent]:
        """
        Get all registered agents.
        
        Args:
            healthy_only: Only return healthy agents
            
        Returns:
            List of all agents
        """
        agents = list(self._agents.values())
        
        if healthy_only:
            agents = [agent for agent in agents if self.is_healthy(agent.agent_id)]
        
        return agents
    
    def update_health(self, agent_id: str):
        """
        Update health check timestamp for an agent.
        
        Args:
            agent_id: Agent ID
        """
        self._health_checks[agent_id] = datetime.utcnow()
    
    def is_healthy(self, agent_id: str) -> bool:
        """
        Check if an agent is healthy.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            True if agent is healthy, False otherwise
        """
        if agent_id not in self._health_checks:
            return False
        
        last_check = self._health_checks[agent_id]
        return datetime.utcnow() - last_check < self._health_timeout
    
    def get_capabilities(self) -> Set[CapabilityType]:
        """
        Get all available capability types.
        
        Returns:
            Set of all capability types
        """
        return set(self._capability_index.keys())
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get registry statistics.
        
        Returns:
            Dictionary with registry stats
        """
        healthy_count = sum(1 for agent_id in self._agents.keys() if self.is_healthy(agent_id))
        
        return {
            "total_agents": len(self._agents),
            "healthy_agents": healthy_count,
            "unhealthy_agents": len(self._agents) - healthy_count,
            "capabilities": [cap.value for cap in self.get_capabilities()],
            "agents_by_capability": {
                cap.value: len(agents)
                for cap, agents in self._capability_index.items()
            }
        }


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry

