"""
Refactored SearchAgent with Smart A2A communication.
Specialized agent for Elasticsearch hybrid search.
"""
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.stores.elasticsearch_store import ElasticsearchStore
from src.processors.embedding_generator import EmbeddingGenerator
from Refactored.config import USE_GPU, EMBEDDING_BATCH_SIZE, ELASTICSEARCH_ENABLED
from Refactored.src.agents.base.base_agent import BaseAgent
from Refactored.src.agents.base.agent_message import AgentMessage, AgentResponse
from Refactored.src.agents.base.agent_capability import AgentCapability, CapabilityType
from Refactored.logger_config import logger


class SearchAgent(BaseAgent):
    """
    Refactored SearchAgent with Smart A2A communication.
    Specialized agent for performing hybrid search in Elasticsearch.
    Combines semantic (vector) and keyword (BM25) search for optimal results.
    """
    
    def __init__(
        self,
        agent_id: str = "search_agent",
        elasticsearch_store: Optional[ElasticsearchStore] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None
    ):
        """
        Initialize SearchAgent.
        
        Args:
            agent_id: Unique agent identifier
            elasticsearch_store: Elasticsearch store instance (auto-created if None)
            embedding_generator: Embedding generator (auto-created if None)
        """
        super().__init__(
            agent_id=agent_id,
            name="SearchAgent",
            description="Specialized agent for Elasticsearch hybrid search"
        )
        
        if not ELASTICSEARCH_ENABLED:
            logger.warning("Elasticsearch not enabled, SearchAgent may not work properly")
        
        self.elasticsearch_store = elasticsearch_store or ElasticsearchStore()
        
        device = USE_GPU if USE_GPU != 'auto' else None
        self.embedding_generator = embedding_generator or EmbeddingGenerator(
            device=device,
            batch_size=EMBEDDING_BATCH_SIZE
        )
        
        # Register capabilities
        self.register_capability(AgentCapability(
            capability_type=CapabilityType.SEARCH,
            description="Perform hybrid search combining semantic and keyword search",
            parameters={
                "query": "str - Search query text",
                "top_k": "int - Number of results (default: 15)",
                "doc_id": "Optional[str] - Filter by document ID",
                "doc_filename": "Optional[str] - Filter by filename"
            },
            returns="Dict with 'query', 'results', 'count', 'search_type'"
        ))
        
        # Register message handlers
        self.register_message_handler("search", self._handle_search)
        self.register_message_handler("hybrid_search", self._handle_search)
        
        logger.info(f"🔍 SearchAgent {agent_id} initialized with A2A support")
    
    async def process_message(self, message: AgentMessage) -> AgentResponse:
        """
        Process incoming messages.
        
        Args:
            message: Incoming message
            
        Returns:
            AgentResponse
        """
        if message.action in ["search", "hybrid_search"]:
            return await self._handle_search(message)
        else:
            return AgentResponse.error_response(
                f"Unknown action: {message.action}",
                error_code="UNKNOWN_ACTION"
            )
    
    async def _handle_search(self, message: AgentMessage) -> AgentResponse:
        """
        Handle search request.
        
        Args:
            message: Search request message
            
        Returns:
            AgentResponse with search results
        """
        try:
            payload = message.payload
            query = payload.get("query", "")
            top_k = payload.get("top_k", 15)
            doc_id = payload.get("doc_id")
            doc_filename = payload.get("doc_filename")
            
            if not query:
                return AgentResponse.error_response(
                    "Query parameter is required",
                    error_code="MISSING_QUERY"
                )
            
            # Perform search in executor to avoid blocking event loop
            # (embedding generation and Elasticsearch I/O are blocking operations)
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # Use default executor (ThreadPoolExecutor)
                lambda: self.search(
                    query=query,
                    top_k=top_k,
                    doc_id=doc_id,
                    doc_filename=doc_filename
                )
            )
            
            return AgentResponse.success_response(
                data=result,
                metadata={
                    "query": query,
                    "result_count": result.get("count", 0)
                }
            )
        except Exception as e:
            logger.error(f"Error in SearchAgent._handle_search: {e}", exc_info=True)
            return AgentResponse.error_response(str(e))
    
    def search(
        self,
        query: str,
        top_k: int = 15,
        doc_id: Optional[str] = None,
        doc_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform hybrid search combining semantic and keyword search.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            doc_id: Optional document ID filter
            doc_filename: Optional filename filter
            
        Returns:
            {
                "query": str,
                "results": List[Dict[str, Any]],  # List of matching chunks
                "count": int,
                "search_type": "hybrid"
            }
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_generator.generate_embedding(query)
            
            # Perform hybrid search (semantic + keyword)
            results = self.elasticsearch_store.hybrid_search(
                query=query,
                query_embedding=query_embedding,
                top_k=top_k,
                doc_id=doc_id,
                doc_filename=doc_filename
            )
            
            logger.info(f"🔍 SearchAgent found {len(results)} results for query: {query[:50]}...")
            
            return {
                "query": query,
                "results": results,
                "count": len(results),
                "search_type": "hybrid"
            }
        except Exception as e:
            logger.error(f"Error in SearchAgent.search: {e}", exc_info=True)
            return {
                "query": query,
                "results": [],
                "count": 0,
                "search_type": "hybrid",
                "error": str(e)
            }
    
    def close(self):
        """Close connections."""
        self.stop()
        if self.elasticsearch_store:
            self.elasticsearch_store.close()

