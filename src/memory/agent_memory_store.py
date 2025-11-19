"""
Agent Memory Store - Long-term memory for successful multi-agent analyses.
Stores successful analyses in Elasticsearch for future retrieval and learning.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.stores.elasticsearch_store import ElasticsearchStore
from src.processors.embedding_generator import EmbeddingGenerator
from config import USE_GPU, EMBEDDING_BATCH_SIZE, ELASTICSEARCH_ENABLED
from logger_config import logger


class AgentMemoryStore:
    """
    Stores successful agent analyses in Elasticsearch for long-term memory.
    Enables semantic search over past successful solutions.
    """
    
    def __init__(self,
                 elasticsearch_store: Optional[ElasticsearchStore] = None,
                 embedding_generator: Optional[EmbeddingGenerator] = None):
        """
        Initialize AgentMemoryStore.
        
        Args:
            elasticsearch_store: Elasticsearch store instance (auto-created if None)
            embedding_generator: Embedding generator (auto-created if None)
        """
        if not ELASTICSEARCH_ENABLED:
            raise ValueError("Elasticsearch must be enabled for AgentMemoryStore")
        
        self.elasticsearch_store = elasticsearch_store or ElasticsearchStore()
        self.index_name = "agent-memory"
        
        device = USE_GPU if USE_GPU != 'auto' else None
        self.embedding_generator = embedding_generator or EmbeddingGenerator(
            device=device,
            batch_size=EMBEDDING_BATCH_SIZE
        )
        
        self._initialize_index()
        logger.info("🧠 AgentMemoryStore initialized")
    
    def _initialize_index(self):
        """Initialize agent-memory index with proper mappings."""
        try:
            if not self.elasticsearch_store.client.indices.exists(index=self.index_name):
                mapping = {
                    "mappings": {
                        "properties": {
                            "query": {
                                "type": "text",
                                "analyzer": "standard",
                                "fields": {
                                    "keyword": {"type": "keyword"}
                                }
                            },
                            "content": {
                                "type": "text",
                                "analyzer": "standard"
                            },
                            "quality_score": {"type": "float"},
                            "sources_used": {"type": "keyword"},
                            "iteration": {"type": "integer"},
                            "timestamp": {"type": "date"},
                            "embedding": {
                                "type": "dense_vector",
                                "dims": self.embedding_generator.model.get_sentence_embedding_dimension(),
                                "index": True,
                                "similarity": "cosine"
                            }
                        }
                    },
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0
                    }
                }
                
                self.elasticsearch_store.client.indices.create(
                    index=self.index_name,
                    **mapping
                )
                logger.info(f"Created index: {self.index_name}")
            else:
                logger.debug(f"Index {self.index_name} already exists")
        except Exception as e:
            logger.error(f"Error initializing agent-memory index: {e}", exc_info=True)
    
    def store_successful_analysis(self,
                                  query: str,
                                  analysis: str,
                                  quality_score: float,
                                  sources_used: List[str],
                                  iteration: int,
                                  metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Store a successful analysis in long-term memory.
        Only stores analyses that meet quality threshold.
        
        Args:
            query: Original query
            analysis: Successful analysis
            quality_score: Quality score (should be >= threshold)
            sources_used: List of source documents used
            iteration: Iteration number when finalized
            metadata: Optional additional metadata
            
        Returns:
            True if stored successfully
        """
        try:
            # Generate embedding for semantic search
            content_for_embedding = f"{query}\n{analysis}"
            embedding = self.embedding_generator.generate_embedding(content_for_embedding)
            
            # Create document
            doc = {
                "query": query,
                "content": analysis,
                "quality_score": quality_score,
                "sources_used": sources_used,
                "iteration": iteration,
                "timestamp": datetime.utcnow().isoformat(),
                "embedding": embedding
            }
            
            if metadata:
                doc["metadata"] = metadata
            
            # Store in Elasticsearch
            doc_id = f"memory_{datetime.utcnow().timestamp()}"
            self.elasticsearch_store.client.index(
                index=self.index_name,
                id=doc_id,
                document=doc
            )
            
            logger.info(f"🧠 Stored successful analysis in agent-memory (quality: {quality_score:.2f})")
            return True
        except Exception as e:
            logger.error(f"Error storing analysis in agent-memory: {e}", exc_info=True)
            return False
    
    def retrieve_similar_memories(self,
                                 query: str,
                                 top_k: int = 3,
                                 min_quality: float = 0.8) -> List[Dict[str, Any]]:
        """
        Retrieve similar past successful analyses using semantic search.
        
        Args:
            query: Query to find similar memories for
            top_k: Number of memories to retrieve
            min_quality: Minimum quality score to consider
            
        Returns:
            List of similar memories with scores
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_generator.generate_embedding(query)
            
            # Build kNN query
            knn_query = {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": top_k * 2,  # Get more candidates to filter
                "num_candidates": top_k * 20
            }
            
            # Add quality filter
            filter_clause = {
                "range": {
                    "quality_score": {
                        "gte": min_quality
                    }
                }
            }
            knn_query["filter"] = filter_clause
            
            # Execute search
            response = self.elasticsearch_store.client.search(
                index=self.index_name,
                knn=knn_query,
                size=top_k,
                source=["query", "content", "quality_score", "sources_used", "iteration", "timestamp"]
            )
            
            # Process results
            memories = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                memories.append({
                    "query": source.get("query", ""),
                    "content": source.get("content", ""),
                    "quality_score": source.get("quality_score", 0.0),
                    "sources_used": source.get("sources_used", []),
                    "iteration": source.get("iteration", 1),
                    "timestamp": source.get("timestamp", ""),
                    "score": float(hit["_score"]),
                    "metadata": source.get("metadata", {})
                })
            
            logger.info(f"🧠 Retrieved {len(memories)} similar memories for query: {query[:50]}...")
            return memories
        except Exception as e:
            logger.error(f"Error retrieving similar memories: {e}", exc_info=True)
            return []
    
    def close(self):
        """Close connections."""
        if self.elasticsearch_store:
            self.elasticsearch_store.close()

