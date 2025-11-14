"""
Shared document storage - documents uploaded by users are shared across all users.
"""
from typing import List, Dict, Any
from neo4j import GraphDatabase
from datetime import datetime
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


class DocumentStore:
    """Store shared documents uploaded by users."""
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize document store."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize document schema."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT shared_doc_id IF NOT EXISTS FOR (d:SharedDocument) REQUIRE d.id IS UNIQUE")
            except:
                pass
    
    def store_document(self,
                     uploaded_by: str,
                     document_data: Dict[str, Any],
                     embeddings: List[List[float]]) -> str:
        """
        Store a shared document.
        
        Args:
            uploaded_by: User ID who uploaded
            document_data: Document data (from document_processor)
            embeddings: Embeddings for chunks
            
        Returns:
            Document ID
        """
        doc_id = f"shared_doc_{datetime.now().timestamp()}"
        
        with self.driver.session() as session:
            # Create user node
            session.run("MERGE (u:User {id: $user_id})", user_id=uploaded_by)
            
            # Create shared document node
            session.run("""
                CREATE (d:SharedDocument {
                    id: $doc_id,
                    file_name: $file_name,
                    file_path: $file_path,
                    file_type: $file_type,
                    uploaded_by: $uploaded_by,
                    uploaded_at: datetime(),
                    text: $text
                })
                WITH d
                MATCH (u:User {id: $uploaded_by})
                CREATE (u)-[:UPLOADED]->(d)
            """,
                doc_id=doc_id,
                file_name=document_data['metadata']['file_name'],
                file_path=document_data['metadata']['file_path'],
                file_type=document_data['metadata']['file_type'],
                uploaded_by=uploaded_by,
                text=document_data['text'][:10000]
            )
            
            # Create chunks (shared across all users)
            for i, (chunk, embedding) in enumerate(zip(document_data['chunks'], embeddings)):
                chunk_id = f"{doc_id}_chunk_{i}"
                
                session.run("""
                    CREATE (c:SharedChunk {
                        id: $chunk_id,
                        text: $text,
                        chunk_index: $chunk_index,
                        embedding: $embedding
                    })
                    WITH c
                    MATCH (d:SharedDocument {id: $doc_id})
                    CREATE (d)-[:CONTAINS]->(c)
                """,
                    chunk_id=chunk_id,
                    text=chunk['text'],
                    chunk_index=chunk['chunk_index'],
                    embedding=embedding,
                    doc_id=doc_id
                )
        
        return doc_id
    
    def similarity_search_shared(self,
                                query_embedding: List[float],
                                top_k: int = 5,
                                doc_id: str = None,
                                doc_filename: str = None) -> List[Dict[str, Any]]:
        """
        Search shared documents using similarity.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            doc_id: Optional document ID to filter by
            doc_filename: Optional document filename to filter by
        """
        import numpy as np
        
        # Similar to neo4j_store.py but for SharedChunk nodes
        with self.driver.session() as session:
            # Build query with optional document filter
            cypher = """
                MATCH (c:SharedChunk)<-[:CONTAINS]-(d:SharedDocument)
                WHERE c.embedding IS NOT NULL
            """
            
            params = {}
            if doc_id:
                cypher += " AND d.id = $doc_id"
                params["doc_id"] = doc_id
            elif doc_filename:
                cypher += " AND d.file_name = $doc_filename"
                params["doc_filename"] = doc_filename
            
            cypher += """
                RETURN c.text AS text,
                       c.chunk_index AS chunk_index,
                       c.id AS chunk_id,
                       c.embedding AS embedding,
                       d.file_name AS file_name,
                       d.id AS doc_id,
                       d.uploaded_by AS uploaded_by
            """
            
            result = session.run(cypher, **params)
            
            import numpy as np
            
            # Batch process for speed
            records = list(result)
            if not records:
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
                    "uploaded_by": record["uploaded_by"],
                    "score": float(similarities_scores[i])
                })
            
            # Ensure top_k is an integer (handle None, float, etc.)
            if top_k is None:
                top_k = 5
            top_k = int(top_k)
            
            # Sort by similarity and return top_k (use numpy argsort for speed)
            top_indices = np.argsort(similarities_scores)[::-1][:top_k]
            return [similarities[i] for i in top_indices]
    
    def get_all_shared_documents(self) -> List[Dict[str, Any]]:
        """Get all shared documents (for admin)."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:SharedDocument)
                OPTIONAL MATCH (d)-[:CONTAINS]->(c:SharedChunk)
                WITH d, count(c) AS chunk_count
                RETURN d.id AS id,
                       d.file_name AS file_name,
                       d.uploaded_by AS uploaded_by,
                       toString(d.uploaded_at) AS uploaded_at,
                       chunk_count
                ORDER BY d.uploaded_at DESC
            """)
            
            documents = []
            for record in result:
                doc = {
                    'id': record.get('id', ''),
                    'file_name': record.get('file_name', 'Unknown'),
                    'uploaded_by': record.get('uploaded_by', 'Unknown'),
                    'uploaded_at': record.get('uploaded_at', ''),
                    'chunk_count': record.get('chunk_count', 0)
                }
                documents.append(doc)
            
            return documents
    
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific shared document."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:SharedDocument {id: $doc_id})-[:CONTAINS]->(c:SharedChunk)
                RETURN c.id AS chunk_id,
                       c.text AS text,
                       c.chunk_index AS chunk_index
                ORDER BY c.chunk_index ASC
            """, doc_id=doc_id)
            
            chunks = []
            for record in result:
                chunk = {
                    'chunk_id': record.get('chunk_id', ''),
                    'text': record.get('text', ''),
                    'chunk_index': record.get('chunk_index', 0)
                }
                chunks.append(chunk)
            
            return chunks
    
    def find_relevant_documents(self,
                                query_embedding: List[float],
                                top_k: int = 3,
                                min_score: float = 0.3) -> List[Dict[str, Any]]:
        """
        Find the most relevant documents based on semantic similarity to the query.
        This searches through all document chunks and returns documents that have
        highly relevant chunks.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Maximum number of documents to return
            min_score: Minimum average similarity score for a document to be considered
            
        Returns:
            List of documents with relevance scores, sorted by relevance
        """
        import numpy as np
        
        with self.driver.session() as session:
            # Get all chunks with their document info
            result = session.run("""
                MATCH (c:SharedChunk)<-[:CONTAINS]-(d:SharedDocument)
                WHERE c.embedding IS NOT NULL
                RETURN c.text AS text,
                       c.embedding AS embedding,
                       d.id AS doc_id,
                       d.file_name AS file_name,
                       d.uploaded_at AS uploaded_at
            """)
            
            records = list(result)
            if not records:
                return []
            
            # Group chunks by document
            doc_chunks = {}
            for record in records:
                doc_id = record["doc_id"]
                if doc_id not in doc_chunks:
                    doc_chunks[doc_id] = {
                        'doc_id': doc_id,
                        'file_name': record["file_name"],
                        'uploaded_at': record["uploaded_at"],
                        'chunks': []
                    }
                doc_chunks[doc_id]['chunks'].append({
                    'text': record["text"],
                    'embedding': record["embedding"]
                })
            
            # Calculate relevance score for each document
            query_vec = np.array(query_embedding, dtype=np.float32)
            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                query_norm = 1.0
            
            scored_documents = []
            for doc_id, doc_data in doc_chunks.items():
                # Calculate similarity for each chunk in this document
                chunk_similarities = []
                for chunk in doc_data['chunks']:
                    chunk_embedding = np.array(chunk['embedding'], dtype=np.float32)
                    chunk_norm = np.linalg.norm(chunk_embedding)
                    if chunk_norm == 0:
                        continue
                    
                    similarity = np.dot(chunk_embedding, query_vec) / (chunk_norm * query_norm)
                    chunk_similarities.append(float(similarity))
                
                if not chunk_similarities:
                    continue
                
                # Use max similarity (best matching chunk) as document relevance score
                # This ensures documents with at least one highly relevant chunk are prioritized
                max_similarity = max(chunk_similarities)
                avg_similarity = sum(chunk_similarities) / len(chunk_similarities)
                
                # Combined score: 70% max, 30% avg (prioritize documents with at least one great match)
                combined_score = (max_similarity * 0.7) + (avg_similarity * 0.3)
                
                if combined_score >= min_score:
                    scored_documents.append({
                        'doc_id': doc_id,
                        'file_name': doc_data['file_name'],
                        'uploaded_at': str(doc_data['uploaded_at']) if doc_data['uploaded_at'] else '',
                        'score': combined_score,
                        'max_chunk_score': max_similarity,
                        'avg_chunk_score': avg_similarity,
                        'chunk_count': len(doc_data['chunks'])
                    })
            
            # Sort by score (descending) and return top_k
            scored_documents.sort(key=lambda x: x['score'], reverse=True)
            return scored_documents[:top_k]
    
    def close(self):
        """Close connection."""
        self.driver.close()

"""
Shared document storage - documents uploaded by users are shared across all users.
"""
from typing import List, Dict, Any
from neo4j import GraphDatabase
from datetime import datetime
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


class DocumentStore:
    """Store shared documents uploaded by users."""
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize document store."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize document schema."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT shared_doc_id IF NOT EXISTS FOR (d:SharedDocument) REQUIRE d.id IS UNIQUE")
            except:
                pass
    
    def store_document(self,
                     uploaded_by: str,
                     document_data: Dict[str, Any],
                     embeddings: List[List[float]]) -> str:
        """
        Store a shared document.
        
        Args:
            uploaded_by: User ID who uploaded
            document_data: Document data (from document_processor)
            embeddings: Embeddings for chunks
            
        Returns:
            Document ID
        """
        doc_id = f"shared_doc_{datetime.now().timestamp()}"
        
        with self.driver.session() as session:
            # Create user node
            session.run("MERGE (u:User {id: $user_id})", user_id=uploaded_by)
            
            # Create shared document node
            session.run("""
                CREATE (d:SharedDocument {
                    id: $doc_id,
                    file_name: $file_name,
                    file_path: $file_path,
                    file_type: $file_type,
                    uploaded_by: $uploaded_by,
                    uploaded_at: datetime(),
                    text: $text
                })
                WITH d
                MATCH (u:User {id: $uploaded_by})
                CREATE (u)-[:UPLOADED]->(d)
            """,
                doc_id=doc_id,
                file_name=document_data['metadata']['file_name'],
                file_path=document_data['metadata']['file_path'],
                file_type=document_data['metadata']['file_type'],
                uploaded_by=uploaded_by,
                text=document_data['text'][:10000]
            )
            
            # Create chunks (shared across all users)
            for i, (chunk, embedding) in enumerate(zip(document_data['chunks'], embeddings)):
                chunk_id = f"{doc_id}_chunk_{i}"
                
                session.run("""
                    CREATE (c:SharedChunk {
                        id: $chunk_id,
                        text: $text,
                        chunk_index: $chunk_index,
                        embedding: $embedding
                    })
                    WITH c
                    MATCH (d:SharedDocument {id: $doc_id})
                    CREATE (d)-[:CONTAINS]->(c)
                """,
                    chunk_id=chunk_id,
                    text=chunk['text'],
                    chunk_index=chunk['chunk_index'],
                    embedding=embedding,
                    doc_id=doc_id
                )
        
        return doc_id
    
    def similarity_search_shared(self,
                                query_embedding: List[float],
                                top_k: int = 5,
                                doc_id: str = None,
                                doc_filename: str = None) -> List[Dict[str, Any]]:
        """
        Search shared documents using similarity.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            doc_id: Optional document ID to filter by
            doc_filename: Optional document filename to filter by
        """
        import numpy as np
        
        # Similar to neo4j_store.py but for SharedChunk nodes
        with self.driver.session() as session:
            # Build query with optional document filter
            cypher = """
                MATCH (c:SharedChunk)<-[:CONTAINS]-(d:SharedDocument)
                WHERE c.embedding IS NOT NULL
            """
            
            params = {}
            if doc_id:
                cypher += " AND d.id = $doc_id"
                params["doc_id"] = doc_id
            elif doc_filename:
                cypher += " AND d.file_name = $doc_filename"
                params["doc_filename"] = doc_filename
            
            cypher += """
                RETURN c.text AS text,
                       c.chunk_index AS chunk_index,
                       c.id AS chunk_id,
                       c.embedding AS embedding,
                       d.file_name AS file_name,
                       d.id AS doc_id,
                       d.uploaded_by AS uploaded_by
            """
            
            result = session.run(cypher, **params)
            
            import numpy as np
            
            # Batch process for speed
            records = list(result)
            if not records:
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
                    "uploaded_by": record["uploaded_by"],
                    "score": float(similarities_scores[i])
                })
            
            # Ensure top_k is an integer (handle None, float, etc.)
            if top_k is None:
                top_k = 5
            top_k = int(top_k)
            
            # Sort by similarity and return top_k (use numpy argsort for speed)
            top_indices = np.argsort(similarities_scores)[::-1][:top_k]
            return [similarities[i] for i in top_indices]
    
    def get_all_shared_documents(self) -> List[Dict[str, Any]]:
        """Get all shared documents (for admin)."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:SharedDocument)
                OPTIONAL MATCH (d)-[:CONTAINS]->(c:SharedChunk)
                WITH d, count(c) AS chunk_count
                RETURN d.id AS id,
                       d.file_name AS file_name,
                       d.uploaded_by AS uploaded_by,
                       toString(d.uploaded_at) AS uploaded_at,
                       chunk_count
                ORDER BY d.uploaded_at DESC
            """)
            
            documents = []
            for record in result:
                doc = {
                    'id': record.get('id', ''),
                    'file_name': record.get('file_name', 'Unknown'),
                    'uploaded_by': record.get('uploaded_by', 'Unknown'),
                    'uploaded_at': record.get('uploaded_at', ''),
                    'chunk_count': record.get('chunk_count', 0)
                }
                documents.append(doc)
            
            return documents
    
    def get_document_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific shared document."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:SharedDocument {id: $doc_id})-[:CONTAINS]->(c:SharedChunk)
                RETURN c.id AS chunk_id,
                       c.text AS text,
                       c.chunk_index AS chunk_index
                ORDER BY c.chunk_index ASC
            """, doc_id=doc_id)
            
            chunks = []
            for record in result:
                chunk = {
                    'chunk_id': record.get('chunk_id', ''),
                    'text': record.get('text', ''),
                    'chunk_index': record.get('chunk_index', 0)
                }
                chunks.append(chunk)
            
            return chunks
    
    def find_relevant_documents(self,
                                query_embedding: List[float],
                                top_k: int = 3,
                                min_score: float = 0.3) -> List[Dict[str, Any]]:
        """
        Find the most relevant documents based on semantic similarity to the query.
        This searches through all document chunks and returns documents that have
        highly relevant chunks.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Maximum number of documents to return
            min_score: Minimum average similarity score for a document to be considered
            
        Returns:
            List of documents with relevance scores, sorted by relevance
        """
        import numpy as np
        
        with self.driver.session() as session:
            # Get all chunks with their document info
            result = session.run("""
                MATCH (c:SharedChunk)<-[:CONTAINS]-(d:SharedDocument)
                WHERE c.embedding IS NOT NULL
                RETURN c.text AS text,
                       c.embedding AS embedding,
                       d.id AS doc_id,
                       d.file_name AS file_name,
                       d.uploaded_at AS uploaded_at
            """)
            
            records = list(result)
            if not records:
                return []
            
            # Group chunks by document
            doc_chunks = {}
            for record in records:
                doc_id = record["doc_id"]
                if doc_id not in doc_chunks:
                    doc_chunks[doc_id] = {
                        'doc_id': doc_id,
                        'file_name': record["file_name"],
                        'uploaded_at': record["uploaded_at"],
                        'chunks': []
                    }
                doc_chunks[doc_id]['chunks'].append({
                    'text': record["text"],
                    'embedding': record["embedding"]
                })
            
            # Calculate relevance score for each document
            query_vec = np.array(query_embedding, dtype=np.float32)
            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                query_norm = 1.0
            
            scored_documents = []
            for doc_id, doc_data in doc_chunks.items():
                # Calculate similarity for each chunk in this document
                chunk_similarities = []
                for chunk in doc_data['chunks']:
                    chunk_embedding = np.array(chunk['embedding'], dtype=np.float32)
                    chunk_norm = np.linalg.norm(chunk_embedding)
                    if chunk_norm == 0:
                        continue
                    
                    similarity = np.dot(chunk_embedding, query_vec) / (chunk_norm * query_norm)
                    chunk_similarities.append(float(similarity))
                
                if not chunk_similarities:
                    continue
                
                # Use max similarity (best matching chunk) as document relevance score
                # This ensures documents with at least one highly relevant chunk are prioritized
                max_similarity = max(chunk_similarities)
                avg_similarity = sum(chunk_similarities) / len(chunk_similarities)
                
                # Combined score: 70% max, 30% avg (prioritize documents with at least one great match)
                combined_score = (max_similarity * 0.7) + (avg_similarity * 0.3)
                
                if combined_score >= min_score:
                    scored_documents.append({
                        'doc_id': doc_id,
                        'file_name': doc_data['file_name'],
                        'uploaded_at': str(doc_data['uploaded_at']) if doc_data['uploaded_at'] else '',
                        'score': combined_score,
                        'max_chunk_score': max_similarity,
                        'avg_chunk_score': avg_similarity,
                        'chunk_count': len(doc_data['chunks'])
                    })
            
            # Sort by score (descending) and return top_k
            scored_documents.sort(key=lambda x: x['score'], reverse=True)
            return scored_documents[:top_k]
    
    def close(self):
        """Close connection."""
        self.driver.close()

