"""
CoordinatorAgent - Orchestrates multi-agent workflows via Smart A2A.
Manages complex workflows involving multiple agents.
"""
from typing import Dict, Any, Optional, List
import asyncio
import time

from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_message import AgentMessage, AgentResponse, MessagePriority
from Refactored.src.agents.base.agent_capability import AgentCapability, CapabilityType
from Refactored.logger_config import logger


class CoordinatorAgent(BaseAgent):
    """
    CoordinatorAgent for orchestrating multi-agent workflows via A2A.
    Manages complex workflows involving multiple specialized agents.
    """
    
    def __init__(self, agent_id: str = "coordinator_agent"):
        """
        Initialize CoordinatorAgent.
        
        Args:
            agent_id: Unique agent identifier
        """
        super().__init__(
            agent_id=agent_id,
            name="CoordinatorAgent",
            description="Orchestrates multi-agent workflows via Smart A2A"
        )
        
        # Register capabilities
        self.register_capability(AgentCapability(
            capability_type=CapabilityType.COORDINATION,
            description="Orchestrate multi-agent workflows",
            parameters={
                "workflow_type": "str - Type of workflow (reflection, rag, etc.)",
                "query": "str - User query",
                "config": "Dict - Workflow configuration"
            },
            returns="Dict with workflow result"
        ))
        
        # Register message handlers
        self.register_message_handler("coordinate_workflow", self._handle_coordinate_workflow)
        self.register_message_handler("reflection_workflow", self._handle_reflection_workflow)
        self.register_message_handler("rag_workflow", self._handle_rag_workflow)
        
        logger.info(f"🎯 CoordinatorAgent {agent_id} initialized")
    
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        """
        Process incoming messages.
        
        Args:
            message: Incoming message
            
        Returns:
            AgentResponse
        """
        if message.action == "coordinate_workflow":
            return await self._handle_coordinate_workflow(message)
        elif message.action == "reflection_workflow":
            return await self._handle_reflection_workflow(message)
        elif message.action == "rag_workflow":
            return await self._handle_rag_workflow(message)
        else:
            return AgentResponse.error_response(
                f"Unknown action: {message.action}",
                error_code="UNKNOWN_ACTION"
            )
    
    async def _handle_coordinate_workflow(self, message: AgentMessage) -> AgentResponse:
        """
        Handle workflow coordination request.
        
        Args:
            message: Coordination request message
            
        Returns:
            AgentResponse with workflow result
        """
        try:
            payload = message.payload
            workflow_type = payload.get("workflow_type", "reflection")
            
            if workflow_type == "reflection":
                return await self._handle_reflection_workflow(message)
            elif workflow_type == "rag":
                return await self._handle_rag_workflow(message)
            else:
                return AgentResponse.error_response(
                    f"Unknown workflow type: {workflow_type}",
                    error_code="UNKNOWN_WORKFLOW"
                )
        except Exception as e:
            logger.error(f"Error in CoordinatorAgent._handle_coordinate_workflow: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
    
    async def _handle_reflection_workflow(
        self,
        message: AgentMessage
    ) -> AgentResponse:
        """
        Handle reflection pattern workflow (Search -> Analyze -> Reflect).
        
        Args:
            message: Workflow request message
            
        Returns:
            AgentResponse with workflow result
        """
        try:
            payload = message.payload
            query = payload.get("query", "")
            max_iterations = payload.get("max_iterations", 3)
            quality_threshold = payload.get("quality_threshold", 0.8)
            top_k = payload.get("top_k", 15)
            
            if not query:
                return AgentResponse.error_response(
                    "Query parameter is required",
                    error_code="MISSING_QUERY"
                )
            
            logger.info(f"🎯 Starting reflection workflow for query: {query[:50]}...")
            start_time = time.time()
            
            iteration = 1
            analysis = None
            quality_score = 0.0
            
            while iteration <= max_iterations:
                # Step 1: Search via SearchAgent
                search_response = await self.delegate_to_agent(
                    capability_type=CapabilityType.SEARCH,
                    action="search",
                    payload={"query": query, "top_k": top_k}
                )
                
                if not search_response or not search_response.success:
                    return AgentResponse.error_response(
                        f"Search failed: {search_response.error if search_response else 'No response'}",
                        error_code="SEARCH_FAILED"
                    )
                
                search_results = search_response.data.get("results", [])
                
                # Step 2: Analyze via AnalyserAgent
                feedback = None
                if iteration > 1 and analysis:
                    # Get feedback from previous reflection
                    feedback = f"Iteration {iteration - 1} analysis needs improvement. Quality score: {quality_score:.2f}"
                
                analyse_response = await self.delegate_to_agent(
                    capability_type=CapabilityType.ANALYSIS,
                    action="analyze",
                    payload={
                        "query": query,
                        "search_results": search_results,
                        "feedback": feedback,
                        "iteration": iteration
                    }
                )
                
                if not analyse_response or not analyse_response.success:
                    return AgentResponse.error_response(
                        f"Analysis failed: {analyse_response.error if analyse_response else 'No response'}",
                        error_code="ANALYSIS_FAILED"
                    )
                
                analysis_data = analyse_response.data
                analysis = analysis_data.get("analysis", "")
                
                # Step 3: Reflect via ReflectionAgent
                reflect_response = await self.delegate_to_agent(
                    capability_type=CapabilityType.REFLECTION,
                    action="evaluate",
                    payload={
                        "query": query,
                        "analysis": analysis,
                        "search_results": search_results,
                        "iteration": iteration
                    }
                )
                
                if not reflect_response or not reflect_response.success:
                    return AgentResponse.error_response(
                        f"Reflection failed: {reflect_response.error if reflect_response else 'No response'}",
                        error_code="REFLECTION_FAILED"
                    )
                
                evaluation = reflect_response.data
                quality_score = evaluation.get("quality_score", 0.0)
                meets_threshold = evaluation.get("meets_threshold", False)
                
                logger.info(f"🎯 Iteration {iteration}: quality={quality_score:.2f}, meets_threshold={meets_threshold}")
                
                if meets_threshold:
                    break
                
                iteration += 1
            
            execution_time = time.time() - start_time
            
            return AgentResponse.success_response(
                data={
                    "query": query,
                    "analysis": analysis,
                    "quality_score": quality_score,
                    "iteration": iteration,
                    "search_results_count": len(search_results),
                    "final_analysis": analysis
                },
                metadata={
                    "workflow_type": "reflection",
                    "execution_time": execution_time,
                    "iterations": iteration
                }
            )
        except Exception as e:
            logger.error(f"Error in CoordinatorAgent._handle_reflection_workflow: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
    
    async def _handle_rag_workflow(self, message: AgentMessage) -> AgentResponse:
        """
        Handle RAG workflow (Search -> Generate).
        
        Args:
            message: RAG workflow request message
            
        Returns:
            AgentResponse with RAG result
        """
        try:
            payload = message.payload
            query = payload.get("query", "")
            top_k = payload.get("top_k", 10)
            
            if not query:
                return AgentResponse.error_response(
                    "Query parameter is required",
                    error_code="MISSING_QUERY"
                )
            
            # Delegate search to SearchAgent
            search_response = await self.delegate_to_agent(
                capability_type=CapabilityType.SEARCH,
                action="search",
                payload={"query": query, "top_k": top_k}
            )
            
            if not search_response or not search_response.success:
                return AgentResponse.error_response(
                    f"Search failed: {search_response.error if search_response else 'No response'}",
                    error_code="SEARCH_FAILED"
                )
            
            search_results = search_response.data.get("results", [])
            
            return AgentResponse.success_response(
                data={
                    "query": query,
                    "results": search_results,
                    "count": len(search_results)
                },
                metadata={
                    "workflow_type": "rag"
                }
            )
        except Exception as e:
            logger.error(f"Error in CoordinatorAgent._handle_rag_workflow: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))

