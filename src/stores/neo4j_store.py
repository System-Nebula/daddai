"""
Neo4j integration module for storing embeddings and knowledge graph.
"""
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import numpy as np
from config import (
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBEDDING_DIMENSION,
    NEO4J_MAX_CONNECTION_LIFETIME, NEO4J_MAX_CONNECTION_POOL_SIZE
)
from logger_config import logger


class Neo4jStore:
    """Store and retrieve documents and embeddings in Neo4j."""
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """
        Initialize Neo4j connection with connection pooling.
        
        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
        """
        try:
            self.driver = GraphDatabase.driver(
                uri,
                auth=(user, password),
                max_connection_lifetime=NEO4J_MAX_CONNECTION_LIFETIME,
                max_connection_pool_size=NEO4J_MAX_CONNECTION_POOL_SIZE,
                connection_acquisition_timeout=30.0
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
        
        self.embedding_dimension = EMBEDDING_DIMENSION
        self.use_vector_index = False
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize vector index and constraints in Neo4j."""
        with self.driver.session() as session:
            # Create constraints first
            try:
                session.run("CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE")
                session.run("CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE")
            except Exception as e:
                # Constraints might already exist
                logger.debug(f"Constraint creation (may already exist): {e}")
            
            # Try to create vector index (Neo4j 5.x+ with vector plugin)
            try:
                session.run("""
                    CREATE VECTOR INDEX document_embeddings IF NOT EXISTS
                    FOR (c:Chunk) ON c.embedding
                    OPTIONS {
                        indexConfig: {
                            `vector.dimensions`: $dimension,
                            `vector.similarity_function`: 'cosine'
                        }
                    }
                """, dimension=self.embedding_dimension)
                self.use_vector_index = True
                logger.info("Vector index created successfully")
            except Exception as e:
                # Vector index not available, will use cosine similarity calculation
                logger.warning(f"Vector index not available, using cosine similarity calculation: {e}")
                self.use_vector_index = False
    
    def store_document(self, document: Dict[str, Any], embeddings: List[List[float]]) -> str:
        """
        Store a document and its chunks with embeddings in Neo4j.
        
        Args:
            document: Processed document dictionary
            embeddings: List of embeddings for each chunk
            
        Returns:
            Document ID
        """
        # Create safe document ID (remove special characters)
        safe_name = "".join(c if c.isalnum() or c in ('_', '-', '.') else '_' for c in document['metadata']['file_name'])
        doc_id = f"doc_{safe_name}"
        
        try:
            with self.driver.session() as session:
                # Create document node
                session.run("""
                    MERGE (d:Document {id: $doc_id})
                    SET d.file_name = $file_name,
                        d.file_path = $file_path,
                        d.file_type = $file_type,
                        d.text = $text,
                        d.created_at = datetime()
                """, 
                    doc_id=doc_id,
                    file_name=document['metadata']['file_name'],
                    file_path=document['metadata']['file_path'],
                    file_type=document['metadata']['file_type'],
                    text=document['text'][:10000]  # Store first 10k chars
                )
                
                # Create chunk nodes with embeddings (batch for better performance)
                chunks_data = []
                for i, (chunk, embedding) in enumerate(zip(document['chunks'], embeddings)):
                    chunk_id = f"{doc_id}_chunk_{i}"
                    chunks_data.append({
                        'chunk_id': chunk_id,
                        'text': chunk['text'],
                        'chunk_index': chunk['chunk_index'],
                        'embedding': embedding
                    })
                
                # Batch create chunks for better performance
                for chunk_data in chunks_data:
                    session.run("""
                        CREATE (c:Chunk {
                            id: $chunk_id,
                            text: $text,
                            chunk_index: $chunk_index,
                            embedding: $embedding
                        })
                        WITH c
                        MATCH (d:Document {id: $doc_id})
                        CREATE (d)-[:CONTAINS]->(c)
                    """,
                        chunk_id=chunk_data['chunk_id'],
                        text=chunk_data['text'],
                        chunk_index=chunk_data['chunk_index'],
                        embedding=chunk_data['embedding'],
                        doc_id=doc_id
                    )
            
            logger.info(f"Stored document {doc_id} with {len(chunks_data)} chunks")
            return doc_id
        except Exception as e:
            logger.error(f"Error storing document {doc_id}: {e}")
            raise
    
    def similarity_search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using vector similarity.
        
        Args:
            query_embedding: Embedding vector of the query
            top_k: Number of top results to return
            
        Returns:
            List of similar chunks with metadata
        """
        try:
            with self.driver.session() as session:
                if self.use_vector_index:
                    # Use vector index if available
                    try:
                        result = session.run("""
                            CALL db.index.vector.queryNodes('document_embeddings', $k, $query_embedding)
                            YIELD node, score
                            MATCH (node)<-[:CONTAINS]-(doc:Document)
                            RETURN node.text AS text, 
                                   node.chunk_index AS chunk_index,
                                   node.id AS chunk_id,
                                   doc.file_name AS file_name,
                                   doc.id AS doc_id,
                                   score
                            ORDER BY score DESC
                            LIMIT $k
                        """, 
                            k=top_k,
                            query_embedding=query_embedding
                        )
                        
                        results = []
                        for record in result:
                            results.append({
                                "text": record["text"],
                                "chunk_index": record["chunk_index"],
                                "chunk_id": record["chunk_id"],
                                "file_name": record["file_name"],
                                "doc_id": record["doc_id"],
                                "score": float(record["score"])
                            })
                        
                        logger.debug(f"Found {len(results)} results using vector index")
                        return results
                    except Exception as e:
                        logger.warning(f"Vector index query failed, falling back to cosine similarity: {e}")
                        self.use_vector_index = False
                
                # Fallback: Calculate cosine similarity manually (optimized with vectorized operations)
                result = session.run("""
                    MATCH (c:Chunk)<-[:CONTAINS]-(d:Document)
                    WHERE c.embedding IS NOT NULL
                    RETURN c.text AS text,
                           c.chunk_index AS chunk_index,
                           c.id AS chunk_id,
                           c.embedding AS embedding,
                           d.file_name AS file_name,
                           d.id AS doc_id
                """)
                
                # Batch process embeddings for speed
                records = list(result)
                if not records:
                    logger.debug("No chunks found in database")
                    return []
                
                # Vectorized cosine similarity calculation
                query_vec = np.array(query_embedding, dtype=np.float32)
                chunk_embeddings = np.array([record["embedding"] for record in records], dtype=np.float32)
                
                # Normalize query vector once
                query_norm = np.linalg.norm(query_vec)
                if query_norm == 0:
                    query_norm = 1.0
                
                # Compute dot products (vectorized)
                dot_products = np.dot(chunk_embeddings, query_vec)
                
                # Compute norms (vectorized)
                chunk_norms = np.linalg.norm(chunk_embeddings, axis=1)
                chunk_norms = np.where(chunk_norms == 0, 1.0, chunk_norms)
                
                # Cosine similarity (vectorized)
                similarities_scores = dot_products / (chunk_norms * query_norm)
                
                # Create results with scores
                similarities = []
                for i, record in enumerate(records):
                    similarities.append({
                        "text": record["text"],
                        "chunk_index": record["chunk_index"],
                        "chunk_id": record["chunk_id"],
                        "file_name": record["file_name"],
                        "doc_id": record["doc_id"],
                        "score": float(similarities_scores[i])
                    })
                
                # Sort by similarity and return top_k (use numpy argsort for speed)
                top_indices = np.argsort(similarities_scores)[::-1][:top_k]
                results = [similarities[i] for i in top_indices]
                logger.debug(f"Found {len(results)} results using cosine similarity")
                return results
        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            raise
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all stored documents."""
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (d:Document)
                    RETURN d.id AS id, 
                           d.file_name AS file_name,
                           d.file_path AS file_path,
                           d.file_type AS file_type
                """)
                
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Error getting all documents: {e}")
            return []
    
    def delete_document(self, doc_id: str):
        """Delete a document and all its chunks."""
        try:
            with self.driver.session() as session:
                session.run("""
                    MATCH (d:Document {id: $doc_id})
                    DETACH DELETE d
                """, doc_id=doc_id)
            logger.info(f"Deleted document {doc_id}")
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            raise
    
    def close(self):
        """Close the Neo4j connection."""
        try:
            self.driver.close()
            logger.info("Neo4j connection closed")
        except Exception as e:
            logger.error(f"Error closing Neo4j connection: {e}")
