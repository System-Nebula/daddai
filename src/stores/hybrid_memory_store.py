"""
Hybrid memory store that combines Neo4j (for relationships) and Elasticsearch (for search).
Provides faster semantic search for memories while maintaining graph relationships.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import ELASTICSEARCH_ENABLED
from src.stores.memory_store import MemoryStore
from logger_config import logger

# Try to import ElasticsearchStore, but make it optional
try:
    from src.stores.elasticsearch_store import ElasticsearchStore
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    logger.warning("Elasticsearch not available for memories. Install with: pip install elasticsearch>=8.0.0")


class HybridMemoryStore:
    """
    Hybrid memory store that uses:
    - Neo4j for memory metadata and relationships
    - Elasticsearch for high-performance search (if enabled)
    """
    
    def __init__(self):
        """Initialize hybrid memory store."""
        # Always use Neo4j for relationships
        self.neo4j_store = MemoryStore()
        
        # Elasticsearch is optional
        self.elasticsearch_store = None
        if ELASTICSEARCH_ENABLED and ELASTICSEARCH_AVAILABLE:
            try:
                # Create a custom ElasticsearchStore with memory-specific indices
                # We'll create a wrapper that uses different index names
                from elasticsearch import Elasticsearch
                from config import (
                    ELASTICSEARCH_HOST, ELASTICSEARCH_PORT, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD,
                    ELASTICSEARCH_USE_SSL, ELASTICSEARCH_VERIFY_CERTS, EMBEDDING_DIMENSION
                )
                
                # Build connection URL
                scheme = "https" if ELASTICSEARCH_USE_SSL else "http"
                url = f"{scheme}://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"
                
                connection_params = {"request_timeout": 30}
                if ELASTICSEARCH_USE_SSL:
                    connection_params["verify_certs"] = ELASTICSEARCH_VERIFY_CERTS
                else:
                    connection_params["verify_certs"] = False
                
                if ELASTICSEARCH_USER and ELASTICSEARCH_PASSWORD:
                    connection_params["basic_auth"] = (ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD)
                
                es_client = Elasticsearch(url, **connection_params)
                
                # Create a simple wrapper that uses memory indices
                self.elasticsearch_store = type('obj', (object,), {
                    'client': es_client,
                    'index_name': 'memories',
                    'chunk_index_name': 'memory_chunks',
                    'embedding_dimension': EMBEDDING_DIMENSION
                })()
                
                # Initialize memory indices
                self._initialize_memory_indices()
                
                logger.info("✅ Hybrid memory search enabled: Neo4j + Elasticsearch")
            except Exception as e:
                logger.warning(f"⚠️ Elasticsearch not available for memories, falling back to Neo4j only: {e}")
                self.elasticsearch_store = None
        else:
            logger.info("📊 Using Neo4j only for memories (Elasticsearch disabled)")
    
    def _initialize_memory_indices(self):
        """Initialize Elasticsearch indices for memories."""
        if not self.elasticsearch_store:
            return
        
        try:
            # Memory index mapping
            memory_mapping = {
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "doc_id": {"type": "keyword"},  # memory_id
                        "channel_id": {"type": "keyword"},
                        "text": {
                            "type": "text",
                            "analyzer": "standard",
                            "fields": {
                                "english": {
                                    "type": "text",
                                    "analyzer": "english"
                                }
                            }
                        },
                        "memory_type": {"type": "keyword"},
                        "chunk_index": {"type": "integer"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": self.elasticsearch_store.embedding_dimension,
                            "index": True,
                            "similarity": "cosine"
                        },
                        "user_id": {"type": "keyword"},
                        "mentioned_user_id": {"type": "keyword"},
                        "created_at": {"type": "date"}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            }
            
            # Create index if it doesn't exist (don't recreate if it already exists)
            if not self.elasticsearch_store.client.indices.exists(index=self.elasticsearch_store.chunk_index_name):
                self.elasticsearch_store.client.indices.create(
                    index=self.elasticsearch_store.chunk_index_name,
                    **memory_mapping
                )
                logger.info(f"Created memory index: {self.elasticsearch_store.chunk_index_name}")
            else:
                logger.debug(f"Memory index {self.elasticsearch_store.chunk_index_name} already exists")
        except Exception as e:
            logger.error(f"Error initializing memory indices: {e}")
            raise
    
    def store_memory(self,
                    channel_id: str,
                    content: str,
                    embedding: List[float],
                    memory_type: str = "conversation",
                    metadata: Dict[str, Any] = None,
                    channel_name: str = None,
                    user_id: str = None,
                    username: str = None,
                    mentioned_user_id: str = None) -> str:
        """
        Store memory in both Neo4j and Elasticsearch (if enabled).
        """
        # Always store in Neo4j (for relationships)
        memory_id = self.neo4j_store.store_memory(
            channel_id=channel_id,
            content=content,
            embedding=embedding,
            memory_type=memory_type,
            metadata=metadata,
            channel_name=channel_name,
            user_id=user_id,
            username=username,
            mentioned_user_id=mentioned_user_id
        )
        
        # Also store in Elasticsearch if enabled
        if self.elasticsearch_store:
            try:
                from datetime import datetime
                # Store memory directly in Elasticsearch
                memory_doc = {
                    "chunk_id": memory_id,
                    "doc_id": memory_id,
                    "channel_id": channel_id,
                    "text": content,
                    "memory_type": memory_type,
                    "chunk_index": 0,
                    "embedding": embedding,
                    "user_id": user_id or "unknown",
                    "mentioned_user_id": mentioned_user_id,
                    "created_at": datetime.utcnow().isoformat()
                }
                
                self.elasticsearch_store.client.index(
                    index=self.elasticsearch_store.chunk_index_name,
                    id=memory_id,
                    document=memory_doc
                )
                logger.debug(f"✅ Stored memory {memory_id} in Elasticsearch")
            except Exception as e:
                logger.warning(f"Failed to store memory in Elasticsearch: {e}")
                # Continue anyway - Neo4j storage succeeded
        
        return memory_id
    
    def retrieve_relevant_memories(self,
                                  channel_id: str,
                                  query_embedding: List[float],
                                  top_k: int = 5,
                                  min_score: float = 0.5,
                                  memory_types: List[str] = None,
                                  mentioned_user_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories using the best available method.
        - If Elasticsearch is enabled: Use Elasticsearch vector search (faster)
        - Otherwise: Use Neo4j similarity search (fallback)
        
        Args:
            channel_id: Discord channel ID
            query_embedding: Query embedding vector
            top_k: Number of memories to retrieve
            min_score: Minimum similarity score
            memory_types: Filter by memory types (None for all)
            mentioned_user_id: Boost memories mentioning this user ID
        """
        # Use Elasticsearch if available (much faster at scale)
        if self.elasticsearch_store:
            try:
                # Build filter for Elasticsearch query
                filter_clauses = [{"term": {"channel_id": channel_id}}]
                
                # Add memory type filter if specified
                if memory_types:
                    filter_clauses.append({"terms": {"memory_type": memory_types}})
                
                # Add mentioned_user_id boost if specified (boost score for matching memories)
                boost_query = None
                if mentioned_user_id:
                    # Boost memories that mention this user
                    boost_query = {
                        "bool": {
                            "should": [
                                {"term": {"mentioned_user_id": {"value": mentioned_user_id, "boost": 2.0}}}
                            ]
                        }
                    }
                
                # Use kNN search with channel filter
                knn_query = {
                    "field": "embedding",
                    "query_vector": query_embedding,
                    "k": top_k * 2,
                    "num_candidates": top_k * 20,
                    "filter": {
                        "bool": {
                            "must": filter_clauses
                        }
                    }
                }
                
                # Build the search query
                search_params = {
                    "index": self.elasticsearch_store.chunk_index_name,
                    "knn": knn_query,
                    "size": top_k,
                    "source": ["chunk_id", "doc_id", "text", "channel_id", "memory_type", "mentioned_user_id"]
                }
                
                # Add boost query if mentioned_user_id is provided
                if boost_query:
                    search_params["query"] = boost_query
                
                response = self.elasticsearch_store.client.search(**search_params)
                
                results = []
                for hit in response["hits"]["hits"]:
                    score = hit["_score"]
                    if score >= min_score:
                        source = hit["_source"]
                        results.append({
                            "memory_id": source.get("doc_id") or source.get("chunk_id"),
                            "content": source.get("text", ""),
                            "channel_id": source.get("channel_id", channel_id),
                            "memory_type": source.get("memory_type", "conversation"),
                            "mentioned_user_id": source.get("mentioned_user_id"),
                            "score": float(score)
                        })
                
                logger.debug(f"🔍 Elasticsearch memory search returned {len(results)} results")
                return results
            except Exception as e:
                logger.warning(f"Elasticsearch memory search failed, falling back to Neo4j: {e}")
                # Fall through to Neo4j
        
        # Fallback to Neo4j
        return self.neo4j_store.retrieve_relevant_memories(
            channel_id=channel_id,
            query_embedding=query_embedding,
            top_k=top_k,
            memory_types=memory_types,
            mentioned_user_id=mentioned_user_id
        )
    
    def hybrid_search_memories(self,
                               query: str,
                               query_embedding: List[float],
                               channel_id: str,
                               top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (semantic + keyword) on memories.
        """
        if self.elasticsearch_store:
            try:
                # Build hybrid query with RRF
                knn_query = {
                    "field": "embedding",
                    "query_vector": query_embedding,
                    "k": top_k * 2,
                    "num_candidates": top_k * 20,
                    "filter": {
                        "term": {"channel_id": channel_id}
                    }
                }
                
                must_clauses = [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["text^2", "text.english^1.5"],
                            "type": "best_fields",
                            "fuzziness": "AUTO"
                        }
                    },
                    {"term": {"channel_id": channel_id}}
                ]
                
                # Try RRF first (requires paid license), fallback to simple combination if not available
                try:
                    response = self.elasticsearch_store.client.search(
                        index=self.elasticsearch_store.chunk_index_name,
                        knn=knn_query,
                        query={
                            "bool": {
                                "must": must_clauses
                            }
                        },
                        rank={
                            "rrf": {
                                "window_size": top_k * 2,
                                "rank_constant": 60
                            }
                        },
                        size=top_k,
                        source=["chunk_id", "doc_id", "text", "channel_id", "memory_type"]
                    )
                except Exception as rrf_error:
                    # RRF requires paid license, fallback to vector search only
                    if "rrf" in str(rrf_error).lower() or "license" in str(rrf_error).lower() or "non-compliant" in str(rrf_error).lower():
                        logger.debug(f"RRF not available (license issue), using vector search only: {rrf_error}")
                        # Use vector search only (works with free license)
                        response = self.elasticsearch_store.client.search(
                            index=self.elasticsearch_store.chunk_index_name,
                            knn=knn_query,
                            size=top_k,
                            source=["chunk_id", "doc_id", "text", "channel_id", "memory_type"]
                        )
                    else:
                        raise
                
                results = []
                for hit in response["hits"]["hits"]:
                    source = hit["_source"]
                    results.append({
                        "memory_id": source.get("doc_id") or source.get("chunk_id"),
                        "content": source.get("text", ""),
                        "channel_id": source.get("channel_id", channel_id),
                        "memory_type": source.get("memory_type", "conversation"),
                        "score": float(hit["_score"])
                    })
                
                return results
            except Exception as e:
                logger.warning(f"Elasticsearch hybrid memory search failed: {e}")
        
        # Fallback to Neo4j vector search
        return self.retrieve_relevant_memories(channel_id, query_embedding, top_k)
    
    # Delegate all other methods to Neo4j store
    def get_channel_memories(self, channel_id: str = None, channel_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get memories for a channel (from Neo4j - source of truth)."""
        return self.neo4j_store.get_channel_memories(channel_id=channel_id, channel_name=channel_name, limit=limit)
    
    def get_memories_by_channel(self, channel_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get memories for a channel (alias for compatibility)."""
        return self.neo4j_store.get_channel_memories(channel_id=channel_id, limit=limit)
    
    def get_all_channels(self) -> List[Dict[str, Any]]:
        """Get all channels (from Neo4j - source of truth)."""
        return self.neo4j_store.get_all_channels()
    
    def get_all_memories(self, channel_id: str = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all memories (from Neo4j - source of truth)."""
        if channel_id:
            return self.neo4j_store.get_channel_memories(channel_id=channel_id, limit=limit)
        return self.neo4j_store.get_all_memories(limit=limit)
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete memory from both stores."""
        # Delete from Neo4j
        result = self.neo4j_store.delete_memory(memory_id)
        
        # Delete from Elasticsearch if enabled
        if self.elasticsearch_store and result:
            try:
                self.elasticsearch_store.client.delete(
                    index=self.elasticsearch_store.chunk_index_name,
                    id=memory_id,
                    ignore=[404]
                )
            except Exception as e:
                logger.warning(f"Failed to delete memory from Elasticsearch: {e}")
        
        return result
    
    def close(self):
        """Close connections."""
        self.neo4j_store.close()
        if self.elasticsearch_store and hasattr(self.elasticsearch_store, 'client'):
            self.elasticsearch_store.client.close()

