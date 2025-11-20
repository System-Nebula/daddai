"""
Refactored RAG Pipeline with agent integration.
Cleaner separation of concerns with agent-based retrieval.
"""
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from Refactored.src.agents.coordinator import CoordinatorAgent
from Refactored.src.agents.base.agent_message import AgentMessage
from Refactored.logger_config import logger


class RAGPipeline:
    """
    Refactored RAG Pipeline with agent integration.
    Uses CoordinatorAgent for workflow orchestration.
    """
    
    def __init__(self, coordinator: Optional[CoordinatorAgent] = None):
        """
        Initialize RAG Pipeline.
        
        Args:
            coordinator: CoordinatorAgent instance (auto-created if None)
        """
        self.coordinator = coordinator or CoordinatorAgent()
        logger.info("📚 RAG Pipeline initialized with agent integration")
    
    async def query(
        self,
        question: str,
        top_k: int = 10,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query the RAG system.
        
        Args:
            question: User question
            top_k: Number of results to retrieve
            context: Additional context
            
        Returns:
            Query result dictionary
        """
        try:
            # Use coordinator to execute RAG workflow
            message = AgentMessage(
                sender_id="rag_pipeline",
                receiver_id=self.coordinator.agent_id,
                action="rag_workflow",
                payload={
                    "query": question,
                    "top_k": top_k,
                    "context": context or {}
                }
            )
            
            response = await self.coordinator.handle_message(message)
            
            if response.success:
                return {
                    "answer": response.data.get("results", []),
                    "context_chunks": len(response.data.get("results", [])),
                    "source_documents": response.data.get("results", [])
                }
            else:
                return {
                    "answer": f"Error: {response.error}",
                    "context_chunks": 0,
                    "source_documents": []
                }
        except Exception as e:
            logger.error(f"Error in RAG Pipeline query: {e}", exc_info=True)
            return {
                "answer": f"Error: {str(e)}",
                "context_chunks": 0,
                "source_documents": []
            }

