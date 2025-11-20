"""
Refactored AnalyserAgent with Smart A2A communication.
Specialized agent for reasoning and analysis generation.
Uses A2A to delegate search tasks to SearchAgent.
"""
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.clients.llm_client_factory import get_default_llm_client
from Refactored.config import RAG_TEMPERATURE, RAG_MAX_TOKENS
from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_message import AgentMessage, AgentResponse
from Refactored.src.agents.base.agent_capability import AgentCapability, CapabilityType
from Refactored.logger_config import logger


class AnalyserAgent(BaseAgent):
    """
    Refactored AnalyserAgent with Smart A2A communication.
    Specialized agent for generating analysis and reasoning based on retrieved context.
    Uses A2A to delegate search tasks to SearchAgent.
    """
    
    def __init__(self, agent_id: str = "analyser_agent", llm_client=None):
        """
        Initialize AnalyserAgent.
        
        Args:
            agent_id: Unique agent identifier
            llm_client: LLM client (auto-created if None)
        """
        super().__init__(
            agent_id=agent_id,
            name="AnalyserAgent",
            description="Specialized agent for generating analysis and reasoning"
        )
        
        self.llm_client = llm_client or get_default_llm_client()
        
        # Register capabilities
        self.register_capability(AgentCapability(
            capability_type=CapabilityType.ANALYSIS,
            description="Generate analysis and reasoning based on search results",
            parameters={
                "query": "str - Original user query",
                "search_results": "List[Dict] - Results from SearchAgent",
                "past_memories": "Optional[List[Dict]] - Past successful analyses",
                "feedback": "Optional[str] - Feedback from ReflectionAgent",
                "iteration": "int - Current iteration number"
            },
            returns="Dict with 'analysis', 'query', 'iteration', 'sources_used', 'confidence'"
        ))
        
        # Register message handlers
        self.register_message_handler("analyze", self._handle_analyze)
        self.register_message_handler("analyze_with_search", self._handle_analyze_with_search)
        
        logger.info(f"🧠 AnalyserAgent {agent_id} initialized with A2A support")
    
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        """
        Process incoming messages.
        
        Args:
            message: Incoming message
            
        Returns:
            AgentResponse
        """
        if message.action == "analyze":
            return await self._handle_analyze(message)
        elif message.action == "analyze_with_search":
            return await self._handle_analyze_with_search(message)
        else:
            return AgentResponse.error_response(
                f"Unknown action: {message.action}",
                error_code="UNKNOWN_ACTION"
            )
    
    async def _handle_analyze(self, message: AgentMessage) -> AgentResponse:
        """
        Handle analyze request (with provided search results).
        
        Args:
            message: Analyze request message
            
        Returns:
            AgentResponse with analysis
        """
        try:
            payload = message.payload
            query = payload.get("query", "")
            search_results = payload.get("search_results", [])
            past_memories = payload.get("past_memories")
            feedback = payload.get("feedback")
            iteration = payload.get("iteration", 1)
            
            if not query:
                return AgentResponse.error_response(
                    "Query parameter is required",
                    error_code="MISSING_QUERY"
                )
            
            # Perform analysis
            result = self.analyze(
                query=query,
                search_results=search_results,
                past_memories=past_memories,
                feedback=feedback,
                iteration=iteration
            )
            
            return AgentResponse.success_response(
                data=result,
                metadata={
                    "query": query,
                    "iteration": iteration,
                    "confidence": result.get("confidence", 0.0)
                }
            )
        except Exception as e:
            logger.error(f"Error in AnalyserAgent._handle_analyze: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
    
    async def _handle_analyze_with_search(self, message: AgentMessage) -> AgentResponse:
        """
        Handle analyze request with automatic search delegation via A2A.
        
        Args:
            message: Analyze request message
            
        Returns:
            AgentResponse with analysis
        """
        try:
            payload = message.payload
            query = payload.get("query", "")
            top_k = payload.get("top_k", 15)
            past_memories = payload.get("past_memories")
            feedback = payload.get("feedback")
            iteration = payload.get("iteration", 1)
            
            if not query:
                return AgentResponse.error_response(
                    "Query parameter is required",
                    error_code="MISSING_QUERY"
                )
            
            # Delegate search to SearchAgent via A2A
            search_response = await self.delegate_to_agent(
                capability_type=CapabilityType.SEARCH,
                action="search",
                payload={
                    "query": query,
                    "top_k": top_k
                }
            )
            
            if not search_response or not search_response.success:
                return AgentResponse.error_response(
                    f"Search failed: {search_response.error if search_response else 'No response'}",
                    error_code="SEARCH_FAILED"
                )
            
            search_results = search_response.data.get("results", [])
            
            # Perform analysis with search results
            result = self.analyze(
                query=query,
                search_results=search_results,
                past_memories=past_memories,
                feedback=feedback,
                iteration=iteration
            )
            
            return AgentResponse.success_response(
                data=result,
                metadata={
                    "query": query,
                    "iteration": iteration,
                    "confidence": result.get("confidence", 0.0),
                    "search_results_count": len(search_results)
                }
            )
        except Exception as e:
            logger.error(f"Error in AnalyserAgent._handle_analyze_with_search: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
    
    def analyze(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        past_memories: Optional[List[Dict[str, Any]]] = None,
        feedback: Optional[str] = None,
        iteration: int = 1
    ) -> Dict[str, Any]:
        """
        Generate analysis based on search results and optional feedback.
        
        Args:
            query: Original user query
            search_results: Results from SearchAgent
            past_memories: Optional past successful analyses (for learning)
            feedback: Optional feedback from ReflectionAgent (for iteration)
            iteration: Current iteration number
            
        Returns:
            {
                "analysis": str,
                "query": str,
                "iteration": int,
                "sources_used": List[str],
                "confidence": float
            }
        """
        try:
            # Build context from search results
            context_chunks = []
            sources_used = []
            
            for result in search_results[:10]:  # Use top 10 results
                text = result.get("text", "")
                file_name = result.get("file_name", "unknown")
                chunk_id = result.get("chunk_id", "")
                
                if text:
                    context_chunks.append(f"[From {file_name}]: {text}")
                    if file_name not in sources_used:
                        sources_used.append(file_name)
            
            context_text = "\n\n".join(context_chunks)
            
            # Build prompt with optional past memories
            memory_context = ""
            if past_memories:
                memory_context = "\n\n## Similar Past Solutions:\n"
                for i, memory in enumerate(past_memories[:3], 1):  # Top 3 similar memories
                    memory_context += f"\n{i}. {memory.get('content', '')[:300]}...\n"
            
            # Build feedback context if iterating
            feedback_context = ""
            if feedback and iteration > 1:
                feedback_context = f"\n\n## Feedback from Previous Iteration:\n{feedback}\n\nPlease address this feedback and improve your analysis."
            
            # Build system prompt
            system_prompt = """You are an expert analyst specializing in document analysis and root cause analysis.
Your task is to analyze information from documents and provide clear, accurate, and well-reasoned analysis.

Guidelines:
- Base your analysis strictly on the provided context
- Be specific and cite sources when possible
- If information is missing, acknowledge it rather than guessing
- Structure your analysis logically
- Provide actionable insights when possible"""
            
            # Build user prompt
            user_prompt = f"""## Query:
{query}

## Context from Documents:
{context_text[:3000]}  # Limit context size
{memory_context}
{feedback_context}

## Instructions:
Analyze the query based on the provided context. If you're iterating (iteration {iteration}), incorporate the feedback to improve your analysis.

Provide a clear, well-structured analysis that directly addresses the query."""

            # Generate analysis
            response = self.llm_client.generate_response(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=RAG_TEMPERATURE,
                max_tokens=RAG_MAX_TOKENS * 2  # More tokens for analysis
            )
            
            analysis = response if isinstance(response, str) else response.get("content", str(response))
            
            # Estimate confidence based on context quality
            confidence = min(0.95, 0.5 + (len(search_results) / 20.0))
            
            logger.info(f"🧠 AnalyserAgent generated analysis (iteration {iteration}, confidence: {confidence:.2f})")
            
            return {
                "analysis": analysis,
                "query": query,
                "iteration": iteration,
                "sources_used": sources_used,
                "confidence": confidence,
                "context_length": len(context_text)
            }
        except Exception as e:
            logger.error(f"Error in AnalyserAgent.analyze: {e}", exc_info=True)
            return {
                "analysis": f"Error generating analysis: {str(e)}",
                "query": query,
                "iteration": iteration,
                "sources_used": [],
                "confidence": 0.0,
                "error": str(e)
            }

