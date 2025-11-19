"""
SearchAgent - Specialized agent for Elasticsearch hybrid search.
Part of the multi-agent reflection pattern system.
"""
from typing import List, Dict, Any, Optional
from src.stores.elasticsearch_store import ElasticsearchStore
from src.processors.embedding_generator import EmbeddingGenerator
from config import USE_GPU, EMBEDDING_BATCH_SIZE, ELASTICSEARCH_ENABLED
from logger_config import logger


class SearchAgent:
    """
    Specialized agent for performing hybrid search in Elasticsearch.
    Combines semantic (vector) and keyword (BM25) search for optimal results.
    """
    
    def __init__(self, 
                 elasticsearch_store: Optional[ElasticsearchStore] = None,
                 embedding_generator: Optional[EmbeddingGenerator] = None):
        """
        Initialize SearchAgent.
        
        Args:
            elasticsearch_store: Elasticsearch store instance (auto-created if None)
            embedding_generator: Embedding generator (auto-created if None)
        """
        if not ELASTICSEARCH_ENABLED:
            raise ValueError("Elasticsearch must be enabled for SearchAgent")
        
        self.elasticsearch_store = elasticsearch_store or ElasticsearchStore()
        
        device = USE_GPU if USE_GPU != 'auto' else None
        self.embedding_generator = embedding_generator or EmbeddingGenerator(
            device=device,
            batch_size=EMBEDDING_BATCH_SIZE
        )
        
        logger.info("🔍 SearchAgent initialized")
    
    def search(self,
               query: str,
               top_k: int = 15,
               doc_id: Optional[str] = None,
               doc_filename: Optional[str] = None) -> Dict[str, Any]:
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
        if self.elasticsearch_store:
            self.elasticsearch_store.close()

