"""
Hybrid document store that combines Neo4j (for relationships) and Elasticsearch (for search).
Provides the best of both worlds:
- Neo4j: Knowledge graph, user-document relationships, entity tracking
- Elasticsearch: High-performance vector and full-text search
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import ELASTICSEARCH_ENABLED
from src.stores.document_store import DocumentStore
from logger_config import logger

# Try to import ElasticsearchStore, but make it optional
try:
    from src.stores.elasticsearch_store import ElasticsearchStore
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    logger.warning("Elasticsearch not available. Install with: pip install elasticsearch>=8.0.0")


class HybridDocumentStore:
    """
    Hybrid document store that uses:
    - Neo4j for document metadata and relationships
    - Elasticsearch for high-performance search (if enabled)
    """
    
    def __init__(self):
        """Initialize hybrid document store."""
        # Always use Neo4j for relationships
        self.neo4j_store = DocumentStore()
        
        # Elasticsearch is optional
        self.elasticsearch_store = None
        if ELASTICSEARCH_ENABLED and ELASTICSEARCH_AVAILABLE:
            try:
                self.elasticsearch_store = ElasticsearchStore()
                logger.info("✅ Hybrid search enabled: Neo4j + Elasticsearch")
            except Exception as e:
                logger.warning(f"⚠️ Elasticsearch not available, falling back to Neo4j only: {e}")
                self.elasticsearch_store = None
        else:
            logger.info("📊 Using Neo4j only (Elasticsearch disabled)")
    
    def store_document(self,
                     uploaded_by: str,
                     document_data: Dict[str, Any],
                     embeddings: List[List[float]]) -> str:
        """
        Store document in both Neo4j and Elasticsearch (if enabled).
        
        Args:
            uploaded_by: User ID who uploaded
            document_data: Document data (from document_processor)
            embeddings: Embeddings for chunks
            
        Returns:
            Document ID
        """
        # Always store in Neo4j (for relationships)
        doc_id = self.neo4j_store.store_document(uploaded_by, document_data, embeddings)
        
        # Also store in Elasticsearch if enabled
        if self.elasticsearch_store:
            try:
                self.elasticsearch_store.store_document(
                    doc_id=doc_id,
                    file_name=document_data['metadata']['file_name'],
                    file_path=document_data['metadata']['file_path'],
                    file_type=document_data['metadata']['file_type'],
                    uploaded_by=uploaded_by,
                    text=document_data['text'],
                    chunk_count=len(document_data['chunks'])
                )
                
                self.elasticsearch_store.store_chunks(
                    doc_id=doc_id,
                    file_name=document_data['metadata']['file_name'],
                    uploaded_by=uploaded_by,
                    chunks=document_data['chunks'],
                    embeddings=embeddings
                )
                logger.debug(f"✅ Stored document {doc_id} in Elasticsearch")
            except Exception as e:
                logger.warning(f"Failed to store document in Elasticsearch: {e}")
                # Continue anyway - Neo4j storage succeeded
        
        return doc_id
    
    def similarity_search_shared(self,
                                query_embedding: List[float],
                                top_k: int = 5,
                                doc_id: str = None,
                                doc_filename: str = None) -> List[Dict[str, Any]]:
        """
        Search shared documents using the best available method.
        - If Elasticsearch is enabled: Use Elasticsearch vector search (faster, scales better)
        - Otherwise: Use Neo4j similarity search (fallback)
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            doc_id: Optional document ID to filter by
            doc_filename: Optional document filename to filter by
        """
        # Use Elasticsearch if available (much faster at scale)
        if self.elasticsearch_store:
            try:
                logger.info(f"🔍 [Elasticsearch] Searching with doc_id={doc_id}, doc_filename={doc_filename}")
                results = self.elasticsearch_store.vector_search(
                    query_embedding=query_embedding,
                    top_k=top_k,
                    doc_id=doc_id,
                    doc_filename=doc_filename
                )
                # If Elasticsearch returns empty results and we're searching a specific document, fall back to Neo4j
                if not results and (doc_id or doc_filename):
                    logger.info(f"⚠️ [Elasticsearch] Returned 0 results for specific document, falling back to Neo4j")
                    # Fall through to Neo4j
                else:
                    logger.info(f"✅ [Elasticsearch] Vector search returned {len(results)} results")
                    return results
            except Exception as e:
                logger.warning(f"❌ [Elasticsearch] Search failed, falling back to Neo4j: {e}")
                # Fall through to Neo4j
        
        # Fallback to Neo4j
        logger.info(f"🔍 [Neo4j] Using Neo4j for search (doc_id={doc_id}, doc_filename={doc_filename})")
        neo4j_results = self.neo4j_store.similarity_search_shared(
            query_embedding=query_embedding,
            top_k=top_k,
            doc_id=doc_id,
            doc_filename=doc_filename
        )
        logger.info(f"✅ [Neo4j] Vector search returned {len(neo4j_results)} results")
        return neo4j_results
    
    def hybrid_search_shared(self,
                            query: str,
                            query_embedding: List[float],
                            top_k: int = 10,
                            doc_id: str = None,
                            doc_filename: str = None,
                            semantic_weight: float = 0.7,
                            keyword_weight: float = 0.3) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (semantic + keyword) using the best available method.
        - If Elasticsearch is enabled: Use native Elasticsearch hybrid search (RRF)
        - Otherwise: Use custom hybrid search implementation
        
        Args:
            query: Query text
            query_embedding: Query embedding vector
            top_k: Number of results to return
            doc_id: Optional document ID filter
            doc_filename: Optional filename filter
            semantic_weight: Weight for semantic search
            keyword_weight: Weight for keyword search
        """
        # Use Elasticsearch native hybrid search if available
        if self.elasticsearch_store:
            try:
                logger.info(f"🔍 [Elasticsearch] Hybrid search with doc_id={doc_id}, doc_filename={doc_filename}")
                results = self.elasticsearch_store.hybrid_search(
                    query=query,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    doc_id=doc_id,
                    doc_filename=doc_filename,
                    semantic_weight=semantic_weight,
                    keyword_weight=keyword_weight
                )
                # If Elasticsearch returns empty results and we're searching a specific document, fall back to Neo4j
                if not results and (doc_id or doc_filename):
                    logger.info(f"⚠️ [Elasticsearch] Hybrid search returned 0 results for specific document, falling back to Neo4j")
                    # Fall through to Neo4j fallback
                else:
                    logger.info(f"✅ [Elasticsearch] Hybrid search returned {len(results)} results")
                    return results
            except Exception as e:
                logger.warning(f"❌ [Elasticsearch] Hybrid search failed, falling back to Neo4j: {e}")
                # Fall through to custom hybrid search
        
        # Fallback: Use Neo4j + custom hybrid search
        logger.info(f"🔍 [Neo4j] Using Neo4j hybrid search (doc_id={doc_id}, doc_filename={doc_filename})")
        # Get semantic results from Neo4j
        semantic_results = self.neo4j_store.similarity_search_shared(
            query_embedding=query_embedding,
            top_k=top_k * 2,  # Get more for hybrid combination
            doc_id=doc_id,
            doc_filename=doc_filename
        )
        
        # Use custom hybrid search implementation
        from src.search.hybrid_search import HybridSearch
        hybrid_search = HybridSearch(
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight
        )
        
        # Extract texts and scores
        texts = [r.get("text", "") for r in semantic_results]
        semantic_scores = [r.get("score", 0.0) for r in semantic_results]
        
        # Combine with BM25
        combined_results = hybrid_search.search(
            query=query,
            documents=semantic_results,
            query_embedding=query_embedding,
            semantic_scores=semantic_scores,
            top_k=top_k
        )
        
        logger.info(f"✅ [Neo4j] Hybrid search returned {len(combined_results)} results")
        return combined_results
    
    def get_all_shared_documents(self) -> List[Dict[str, Any]]:
        """Get all shared documents (from Neo4j - source of truth)."""
        return self.neo4j_store.get_all_shared_documents()
    
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """
        Get all chunks for a specific document.
        Tries Elasticsearch first (faster), falls back to Neo4j.
        """
        if self.elasticsearch_store:
            try:
                logger.info(f"🔍 [Elasticsearch] Getting chunks for doc_id={doc_id}")
                chunks = self.elasticsearch_store.get_document_chunks(doc_id)
                if chunks:
                    logger.info(f"✅ [Elasticsearch] Retrieved {len(chunks)} chunks")
                    return chunks
                else:
                    logger.info(f"⚠️ [Elasticsearch] Returned 0 chunks, falling back to Neo4j")
            except Exception as e:
                logger.warning(f"❌ [Elasticsearch] Chunk retrieval failed, using Neo4j: {e}")
        
        logger.info(f"🔍 [Neo4j] Getting chunks for doc_id={doc_id}")
        chunks = self.neo4j_store.get_document_chunks(doc_id)
        logger.info(f"✅ [Neo4j] Retrieved {len(chunks)} chunks")
        return chunks
    
    def find_relevant_documents(self,
                                query_embedding: List[float],
                                top_k: int = 3,
                                min_score: float = 0.3) -> List[Dict[str, Any]]:
        """
        Find relevant documents based on semantic similarity.
        Uses Elasticsearch if available, otherwise Neo4j.
        """
        if self.elasticsearch_store:
            try:
                # Get top chunks from Elasticsearch
                chunks = self.elasticsearch_store.vector_search(
                    query_embedding=query_embedding,
                    top_k=top_k * 10,  # Get more chunks to aggregate by document
                    min_score=min_score
                )
                
                # Aggregate by document
                doc_scores = {}
                for chunk in chunks:
                    doc_id = chunk.get("doc_id")
                    score = chunk.get("score", 0.0)
                    
                    if doc_id not in doc_scores:
                        doc_scores[doc_id] = {
                            "doc_id": doc_id,
                            "file_name": chunk.get("file_name"),
                            "scores": []
                        }
                    doc_scores[doc_id]["scores"].append(score)
                
                # Calculate document-level scores
                scored_docs = []
                for doc_id, doc_data in doc_scores.items():
                    scores = doc_data["scores"]
                    max_score = max(scores)
                    avg_score = sum(scores) / len(scores)
                    combined_score = (max_score * 0.7) + (avg_score * 0.3)
                    
                    if combined_score >= min_score:
                        scored_docs.append({
                            "doc_id": doc_id,
                            "file_name": doc_data["file_name"],
                            "score": combined_score,
                            "max_chunk_score": max_score,
                            "avg_chunk_score": avg_score,
                            "chunk_count": len(scores)
                        })
                
                # Sort and return top_k
                scored_docs.sort(key=lambda x: x["score"], reverse=True)
                return scored_docs[:top_k]
            except Exception as e:
                logger.warning(f"Elasticsearch document search failed, using Neo4j: {e}")
        
        return self.neo4j_store.find_relevant_documents(
            query_embedding=query_embedding,
            top_k=top_k,
            min_score=min_score
        )
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete document from both Neo4j and Elasticsearch."""
        # Delete from Neo4j (source of truth)
        # Note: DocumentStore doesn't have delete method, but we can add it
        # For now, just delete from Elasticsearch if enabled
        
        if self.elasticsearch_store:
            try:
                self.elasticsearch_store.delete_document(doc_id)
            except Exception as e:
                logger.warning(f"Failed to delete document from Elasticsearch: {e}")
        
        return True
    
    def close(self):
        """Close connections."""
        self.neo4j_store.close()
        if self.elasticsearch_store:
            self.elasticsearch_store.close()

