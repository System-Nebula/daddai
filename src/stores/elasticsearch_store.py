"""
Elasticsearch integration for high-performance document search.
Provides:
- Native vector search (kNN)
- Production-grade BM25 full-text search
- Hybrid search (sparse + dense)
- Advanced filtering, faceting, aggregations
- Distributed search capabilities
"""
from typing import List, Dict, Any, Optional
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import numpy as np
from datetime import datetime
from config import (
    ELASTICSEARCH_HOST, ELASTICSEARCH_PORT, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD,
    ELASTICSEARCH_USE_SSL, ELASTICSEARCH_VERIFY_CERTS, EMBEDDING_DIMENSION
)
from logger_config import logger


class ElasticsearchStore:
    """
    Elasticsearch store for document search.
    Provides high-performance vector and full-text search.
    """
    
    def __init__(self,
                 host: str = ELASTICSEARCH_HOST,
                 port: int = ELASTICSEARCH_PORT,
                 username: Optional[str] = ELASTICSEARCH_USER,
                 password: Optional[str] = ELASTICSEARCH_PASSWORD,
                 use_ssl: bool = ELASTICSEARCH_USE_SSL,
                 verify_certs: bool = ELASTICSEARCH_VERIFY_CERTS):
        """
        Initialize Elasticsearch connection.
        
        Args:
            host: Elasticsearch host
            port: Elasticsearch port
            username: Optional username for authentication
            password: Optional password for authentication
            use_ssl: Whether to use SSL
            verify_certs: Whether to verify SSL certificates
        """
        # Build connection URL
        scheme = "https" if use_ssl else "http"
        url = f"{scheme}://{host}:{port}"
        
        # Build connection config for Elasticsearch 8.x
        es_config = {
            "hosts": [url],
            "request_timeout": 30,
            "max_retries": 3,
            "retry_on_timeout": True
        }
        
        # Add authentication if provided
        if username and password:
            es_config["basic_auth"] = (username, password)
        
        # SSL configuration
        if use_ssl:
            es_config["verify_certs"] = verify_certs
            if not verify_certs:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        try:
            # Use simpler initialization for Elasticsearch 8.x
            # Just pass the URL string directly
            connection_params = {
                "request_timeout": 30
            }
            
            # Only add verify_certs if using SSL
            if use_ssl:
                connection_params["verify_certs"] = verify_certs
            else:
                # For HTTP, don't verify certs
                connection_params["verify_certs"] = False
            
            # Add authentication if provided
            if username and password:
                connection_params["basic_auth"] = (username, password)
            
            self.client = Elasticsearch(url, **connection_params)
            
            # Verify connection - try info() first as it's more reliable than ping()
            try:
                info = self.client.info()
                logger.info(f"Connected to Elasticsearch at {url}")
                logger.debug(f"Elasticsearch version: {info.get('version', {}).get('number', 'unknown')}")
            except Exception as conn_error:
                # If info() fails, try ping() as fallback
                try:
                    if not self.client.ping():
                        raise ConnectionError("Elasticsearch ping returned False")
                    logger.info(f"Connected to Elasticsearch at {url} (via ping)")
                except Exception as ping_error:
                    logger.error(f"Connection test failed: {conn_error}")
                    logger.error(f"Ping also failed: {ping_error}")
                    raise ConnectionError(f"Failed to connect to Elasticsearch. URL: {url}, Error: {conn_error}")
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            logger.error(f"URL attempted: {url}")
            logger.error(f"SSL: {use_ssl}, Verify certs: {verify_certs}")
            raise
        
        self.embedding_dimension = EMBEDDING_DIMENSION
        self.index_name = "documents"
        self.chunk_index_name = "document_chunks"
        self._initialize_indices()
    
    def _initialize_indices(self):
        """Initialize Elasticsearch indices with proper mappings."""
        # Document index mapping
        doc_mapping = {
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "file_name": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "file_path": {"type": "keyword"},
                    "file_type": {"type": "keyword"},
                    "uploaded_by": {"type": "keyword"},
                    "uploaded_at": {"type": "date"},
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
                    "chunk_count": {"type": "integer"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "5s"  # OPTIMIZED: Reduce refresh frequency
            }
        }
        
        # Chunk index mapping with vector field
        chunk_mapping = {
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},
                    "file_name": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
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
                    "chunk_index": {"type": "integer"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": self.embedding_dimension,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "uploaded_by": {"type": "keyword"},
                    "uploaded_at": {"type": "date"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "5s",  # OPTIMIZED: Reduce refresh for better write performance
                "index": {
                    "max_result_window": 50000,  # OPTIMIZED: Allow larger result sets
                    "knn": True,  # OPTIMIZED: Enable kNN search
                    "knn.algo_param.ef_search": 100  # OPTIMIZED: kNN search accuracy/speed tradeoff
                }
            }
        }
        
            # Create indices if they don't exist, or verify they have correct mappings
        try:
            # Check if chunk index exists and has correct mapping
            chunk_index_needs_recreation = False
            if self.client.indices.exists(index=self.chunk_index_name):
                try:
                    # Check if the index has the correct dense_vector mapping
                    current_mapping = self.client.indices.get_mapping(index=self.chunk_index_name)
                    mapping_props = current_mapping.get(self.chunk_index_name, {}).get('mappings', {}).get('properties', {})
                    
                    # Check if embedding field exists and has correct type
                    if 'embedding' not in mapping_props:
                        logger.warning(f"Chunk index missing embedding field, will recreate")
                        chunk_index_needs_recreation = True
                    elif mapping_props['embedding'].get('type') != 'dense_vector':
                        logger.warning(f"Chunk index has wrong embedding type, will recreate")
                        chunk_index_needs_recreation = True
                    else:
                        # Index exists and has correct mapping - no need to recreate
                        logger.debug(f"Chunk index {self.chunk_index_name} already exists with correct mapping")
                except Exception as e:
                    logger.debug(f"Could not verify chunk index mapping (non-critical): {e}")
                    # Don't recreate if we can't verify - assume it's fine
            
            # Create document index if it doesn't exist
            if not self.client.indices.exists(index=self.index_name):
                self.client.indices.create(index=self.index_name, **doc_mapping)
                logger.info(f"Created index: {self.index_name}")
            else:
                logger.debug(f"Document index {self.index_name} already exists")
            
            # Create or recreate chunk index only if needed
            if not self.client.indices.exists(index=self.chunk_index_name):
                self.client.indices.create(index=self.chunk_index_name, **chunk_mapping)
                logger.info(f"Created index: {self.chunk_index_name}")
            elif chunk_index_needs_recreation:
                logger.info(f"Recreating {self.chunk_index_name} index with correct settings...")
                self.client.indices.delete(index=self.chunk_index_name, ignore=[404])
                self.client.indices.create(index=self.chunk_index_name, **chunk_mapping)
                logger.info(f"Recreated index: {self.chunk_index_name}")
            else:
                logger.debug(f"Chunk index {self.chunk_index_name} already exists with correct mapping")
        except Exception as e:
            logger.error(f"Error initializing indices: {e}")
            # Only try to recreate if it was a creation error, not a mapping check error
            if not self.client.indices.exists(index=self.chunk_index_name):
                try:
                    self.client.indices.delete(index=self.chunk_index_name, ignore=[404])
                    self.client.indices.create(index=self.chunk_index_name, **chunk_mapping)
                    logger.info(f"Recreated index: {self.chunk_index_name} after error")
                except Exception as retry_error:
                    logger.error(f"Failed to recreate index: {retry_error}")
                    raise
    
    def store_document(self,
                      doc_id: str,
                      file_name: str,
                      file_path: str,
                      file_type: str,
                      uploaded_by: str,
                      text: str,
                      chunk_count: int = 0) -> bool:
        """
        Store document metadata in Elasticsearch.
        
        Args:
            doc_id: Document ID
            file_name: File name
            file_path: File path
            file_type: File type
            uploaded_by: User who uploaded
            text: Document text (first 10k chars)
            chunk_count: Number of chunks
            
        Returns:
            True if successful
        """
        try:
            doc = {
                "doc_id": doc_id,
                "file_name": file_name,
                "file_path": file_path,
                "file_type": file_type,
                "uploaded_by": uploaded_by,
                "uploaded_at": datetime.utcnow().isoformat(),
                "text": text[:10000],  # Store first 10k chars
                "chunk_count": chunk_count
            }
            
            self.client.index(
                index=self.index_name,
                id=doc_id,
                document=doc
            )
            return True
        except Exception as e:
            logger.error(f"Error storing document in Elasticsearch: {e}")
            return False
    
    def store_chunks(self,
                    doc_id: str,
                    file_name: str,
                    uploaded_by: str,
                    chunks: List[Dict[str, Any]],
                    embeddings: List[List[float]]) -> bool:
        """
        Store document chunks with embeddings in Elasticsearch.
        
        Args:
            doc_id: Document ID
            file_name: File name
            uploaded_by: User who uploaded
            chunks: List of chunk dicts with 'text' and 'chunk_index'
            embeddings: List of embedding vectors
            
        Returns:
            True if successful
        """
        try:
            actions = []
            uploaded_at = datetime.utcnow().isoformat()
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = f"{doc_id}_chunk_{chunk.get('chunk_index', i)}"
                
                action = {
                    "_index": self.chunk_index_name,
                    "_id": chunk_id,
                    "_source": {
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "file_name": file_name,
                        "text": chunk.get("text", ""),
                        "chunk_index": chunk.get("chunk_index", i),
                        "embedding": embedding,
                        "uploaded_by": uploaded_by,
                        "uploaded_at": uploaded_at
                    }
                }
                actions.append(action)
            
            # Bulk insert
            success, failed = bulk(self.client, actions, chunk_size=100, raise_on_error=False)
            
            if failed:
                logger.warning(f"Failed to store {len(failed)} chunks in Elasticsearch")
            
            logger.info(f"Stored {success} chunks in Elasticsearch for document {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Error storing chunks in Elasticsearch: {e}")
            return False
    
    def vector_search(self,
                     query_embedding: List[float],
                     top_k: int = 10,
                     doc_id: Optional[str] = None,
                     doc_filename: Optional[str] = None,
                     min_score: float = 0.0) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using kNN.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            doc_id: Optional document ID filter
            doc_filename: Optional filename filter
            min_score: Minimum similarity score
            
        Returns:
            List of matching chunks with scores
        """
        try:
            # Build knn query - OPTIMIZED parameters
            knn_query = {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": top_k,
                "num_candidates": min(top_k * 20, 1000),  # OPTIMIZED: Cap at 1000 for performance
                "boost": 1.0
            }
            
            # Add filters
            if doc_id or doc_filename:
                filter_clause = {}
                if doc_id:
                    filter_clause = {"term": {"doc_id": doc_id}}
                elif doc_filename:
                    filter_clause = {"term": {"file_name.keyword": doc_filename}}
                knn_query["filter"] = filter_clause
            
            # Execute search using knn parameter
            response = self.client.search(
                index=self.chunk_index_name,
                knn=knn_query,
                size=top_k,
                source=["chunk_id", "doc_id", "file_name", "text", "chunk_index", "uploaded_by"]
            )
            
            # Process results
            results = []
            for hit in response["hits"]["hits"]:
                score = hit["_score"]
                if score >= min_score:
                    source = hit["_source"]
                    results.append({
                        "chunk_id": source.get("chunk_id"),
                        "doc_id": source.get("doc_id"),
                        "file_name": source.get("file_name"),
                        "text": source.get("text"),
                        "chunk_index": source.get("chunk_index", 0),
                        "uploaded_by": source.get("uploaded_by"),
                        "score": float(score)
                    })
            
            return results
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    def full_text_search(self,
                        query: str,
                        top_k: int = 10,
                        doc_id: Optional[str] = None,
                        doc_filename: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Perform full-text search using BM25.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            doc_id: Optional document ID filter
            doc_filename: Optional filename filter
            
        Returns:
            List of matching chunks with scores
        """
        try:
            # Build query
            must_clauses = [
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["text^2", "text.english^1.5", "file_name^3"],
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                }
            ]
            
            # Add filters
            if doc_id:
                must_clauses.append({"term": {"doc_id": doc_id}})
            elif doc_filename:
                must_clauses.append({"term": {"file_name.keyword": doc_filename}})
            
            # Execute search
            response = self.client.search(
                index=self.chunk_index_name,
                query={
                    "bool": {
                        "must": must_clauses
                    }
                },
                size=top_k,
                source=["chunk_id", "doc_id", "file_name", "text", "chunk_index", "uploaded_by"]
            )
            
            # Process results
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                results.append({
                    "chunk_id": source.get("chunk_id"),
                    "doc_id": source.get("doc_id"),
                    "file_name": source.get("file_name"),
                    "text": source.get("text"),
                    "chunk_index": source.get("chunk_index", 0),
                    "uploaded_by": source.get("uploaded_by"),
                    "score": float(hit["_score"])
                })
            
            return results
        except Exception as e:
            logger.error(f"Error in full-text search: {e}")
            return []
    
    def hybrid_search(self,
                     query: str,
                     query_embedding: List[float],
                     top_k: int = 10,
                     doc_id: Optional[str] = None,
                     doc_filename: Optional[str] = None,
                     semantic_weight: float = 0.7,
                     keyword_weight: float = 0.3) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector and full-text search.
        Uses Reciprocal Rank Fusion (RRF) to combine results.
        
        Args:
            query: Search query text
            query_embedding: Query embedding vector
            top_k: Number of results to return
            doc_id: Optional document ID filter
            doc_filename: Optional filename filter
            semantic_weight: Weight for semantic search (0-1)
            keyword_weight: Weight for keyword search (0-1)
            
        Returns:
            List of matching chunks with combined scores
        """
        try:
            # Build filter
            filter_clause = None
            if doc_id:
                filter_clause = {"term": {"doc_id": doc_id}}
            elif doc_filename:
                filter_clause = {"term": {"file_name.keyword": doc_filename}}
            
            # Vector search query
            knn_query = {
                "field": "embedding",
                "query_vector": query_embedding,
                "k": top_k * 2,  # Get more candidates
                "num_candidates": top_k * 20
            }
            if filter_clause:
                knn_query["filter"] = filter_clause
            
            # Full-text search query
            must_clauses = [
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["text^2", "text.english^1.5", "file_name^3"],
                        "type": "best_fields",
                        "fuzziness": "AUTO"
                    }
                }
            ]
            if filter_clause:
                must_clauses.append(filter_clause)
            
            # Try RRF first (requires paid license), fallback to vector search if not available
            try:
                # Hybrid query with RRF
                # Execute search with both knn and query
                response = self.client.search(
                    index=self.chunk_index_name,
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
                    source=["chunk_id", "doc_id", "file_name", "text", "chunk_index", "uploaded_by"]
                )
            except Exception as rrf_error:
                # RRF requires paid license, fallback to vector search only
                if "rrf" in str(rrf_error).lower() or "license" in str(rrf_error).lower() or "non-compliant" in str(rrf_error).lower():
                    logger.debug(f"RRF not available (license issue), using vector search only: {rrf_error}")
                    # Use vector search only (works with free license)
                    response = self.client.search(
                        index=self.chunk_index_name,
                        knn=knn_query,
                        size=top_k,
                        source=["chunk_id", "doc_id", "file_name", "text", "chunk_index", "uploaded_by"]
                    )
                else:
                    raise
            
            # Process results
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                results.append({
                    "chunk_id": source.get("chunk_id"),
                    "doc_id": source.get("doc_id"),
                    "file_name": source.get("file_name"),
                    "text": source.get("text"),
                    "chunk_index": source.get("chunk_index", 0),
                    "uploaded_by": source.get("uploaded_by"),
                    "score": float(hit["_score"])
                })
            
            return results
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete document and all its chunks from Elasticsearch."""
        try:
            # Delete document
            self.client.delete(index=self.index_name, id=doc_id, ignore=[404])
            
            # Delete all chunks
            self.client.delete_by_query(
                index=self.chunk_index_name,
                query={
                    "term": {"doc_id": doc_id}
                }
            )
            
            logger.info(f"Deleted document {doc_id} from Elasticsearch")
            return True
        except Exception as e:
            logger.error(f"Error deleting document from Elasticsearch: {e}")
            return False
    
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document."""
        try:
            response = self.client.search(
                index=self.chunk_index_name,
                query={
                    "term": {"doc_id": doc_id}
                },
                sort=[{"chunk_index": {"order": "asc"}}],
                size=10000,  # Large size to get all chunks
                source=["chunk_id", "text", "chunk_index"]
            )
            
            chunks = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                chunks.append({
                    "chunk_id": source.get("chunk_id"),
                    "text": source.get("text"),
                    "chunk_index": source.get("chunk_index", 0)
                })
            
            return chunks
        except Exception as e:
            logger.error(f"Error getting document chunks: {e}")
            return []
    
    def close(self):
        """Close Elasticsearch connection."""
        if hasattr(self, 'client'):
            self.client.close()

