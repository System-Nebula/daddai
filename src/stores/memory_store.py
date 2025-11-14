"""
Long-term memory storage and retrieval using Neo4j and RAG.
Stores channel memories with embeddings for semantic search.
Memories are now organized by Discord channel instead of user.
"""
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import numpy as np
import json
from datetime import datetime
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBEDDING_DIMENSION
from logger_config import logger


class MemoryStore:
    """Store and retrieve long-term memories with RAG-based relevance."""
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize memory store."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.embedding_dimension = EMBEDDING_DIMENSION
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize memory schema in Neo4j."""
        with self.driver.session() as session:
            # Create constraints
            try:
                session.run("CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE")
                session.run("CREATE CONSTRAINT channel_id IF NOT EXISTS FOR (c:Channel) REQUIRE c.id IS UNIQUE")
            except:
                pass
            
            # Try to create vector index for memory embeddings
            try:
                session.run("""
                    CREATE VECTOR INDEX memory_embeddings IF NOT EXISTS
                    FOR (m:Memory) ON m.embedding
                    OPTIONS {
                        indexConfig: {
                            `vector.dimensions`: $dimension,
                            `vector.similarity_function`: 'cosine'
                        }
                    }
                """, dimension=self.embedding_dimension)
                self.use_vector_index = True
            except:
                self.use_vector_index = False
    
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
        Store a memory for a channel.
        
        Args:
            channel_id: Discord channel ID (primary identifier)
            content: Memory content
            embedding: Embedding vector
            memory_type: Type of memory (conversation, fact, preference, etc.)
            metadata: Additional metadata
            channel_name: Discord channel name (optional, for display)
            
        Returns:
            Memory ID
        """
        import uuid
        # Use timestamp + UUID suffix to ensure uniqueness even for concurrent operations
        memory_id = f"memory_{channel_id}_{datetime.now().timestamp()}_{uuid.uuid4().hex[:8]}"
        
        with self.driver.session() as session:
            # Create/update channel node
            session.run("""
                MERGE (c:Channel {id: $channel_id})
                SET c.last_active = datetime(),
                    c.name = COALESCE($channel_name, c.name)
            """, 
                channel_id=channel_id,
                channel_name=channel_name
            )
            
            # Create memory node
            # Serialize metadata as JSON string (Neo4j doesn't accept Map objects)
            metadata_json = json.dumps(metadata) if metadata else "{}"
            
            # Use MERGE to handle potential duplicates gracefully
            try:
                session.run("""
                    MERGE (m:Memory {id: $memory_id})
                    SET m.channel_id = $channel_id,
                        m.content = $content,
                        m.memory_type = $memory_type,
                        m.embedding = $embedding,
                        m.created_at = datetime(),
                        m.metadata = $metadata_json,
                        m.user_id = COALESCE($user_id, null),
                        m.username = COALESCE($username, null),
                        m.mentioned_user_id = COALESCE($mentioned_user_id, null)
                    WITH m
                    MATCH (c:Channel {id: $channel_id})
                    MERGE (c)-[:HAS_MEMORY]->(m)
                """,
                    memory_id=memory_id,
                    channel_id=channel_id,
                    content=content,
                    memory_type=memory_type,
                    embedding=embedding,
                    metadata_json=metadata_json,
                    user_id=user_id,
                    username=username,
                    mentioned_user_id=mentioned_user_id
                )
            except Exception as e:
                # If MERGE still fails (shouldn't happen with UUID), log and retry with new ID
                logger.debug(f"Memory ID collision detected, generating new ID: {e}")
                memory_id = f"memory_{channel_id}_{datetime.now().timestamp()}_{uuid.uuid4().hex[:8]}"
                session.run("""
                    MERGE (m:Memory {id: $memory_id})
                    SET m.channel_id = $channel_id,
                        m.content = $content,
                        m.memory_type = $memory_type,
                        m.embedding = $embedding,
                        m.created_at = datetime(),
                        m.metadata = $metadata_json,
                        m.user_id = COALESCE($user_id, null),
                        m.username = COALESCE($username, null),
                        m.mentioned_user_id = COALESCE($mentioned_user_id, null)
                    WITH m
                    MATCH (c:Channel {id: $channel_id})
                    MERGE (c)-[:HAS_MEMORY]->(m)
                """,
                    memory_id=memory_id,
                    channel_id=channel_id,
                    content=content,
                    memory_type=memory_type,
                    embedding=embedding,
                    metadata_json=metadata_json,
                    user_id=user_id,
                    username=username,
                    mentioned_user_id=mentioned_user_id
                )
        
        return memory_id
    
    def retrieve_relevant_memories(self,
                                  channel_id: str,
                                  query_embedding: List[float],
                                  top_k: int = 5,
                                  memory_types: List[str] = None,
                                  mentioned_user_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant memories using RAG similarity search.
        
        Args:
            channel_id: Discord channel ID
            query_embedding: Query embedding vector
            top_k: Number of memories to retrieve
            memory_types: Filter by memory types (None for all)
            
        Returns:
            List of relevant memories
        """
        with self.driver.session() as session:
            if self.use_vector_index:
                try:
                    # Use vector index if available
                    cypher = """
                        CALL db.index.vector.queryNodes('memory_embeddings', $k, $query_embedding)
                        YIELD node, score
                        WHERE node.channel_id = $channel_id
                    """
                    params = {
                        "k": top_k * 2,  # Get more to filter
                        "query_embedding": query_embedding,
                        "channel_id": channel_id
                    }
                    
                    if memory_types:
                        cypher += " AND node.memory_type IN $memory_types"
                        params["memory_types"] = memory_types
                    
                    cypher += """
                        RETURN node.content AS content,
                               node.memory_type AS memory_type,
                               toString(node.created_at) AS created_at,
                               COALESCE(node.metadata, "{}") AS metadata,
                               node.mentioned_user_id AS mentioned_user_id,
                               score
                        ORDER BY score DESC
                        LIMIT $k
                    """
                    params["k"] = top_k
                    
                    result = session.run(cypher, **params)
                    
                    memories = []
                    for record in result:
                        metadata_str = record.get("metadata", "{}")
                        try:
                            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else (metadata_str or {})
                        except:
                            metadata = {}
                        
                        score = float(record.get("score", 0))
                        # Boost score if this memory mentions the queried user
                        if mentioned_user_id and record.get("mentioned_user_id") == mentioned_user_id:
                            score = score * 1.2
                        
                        memories.append({
                            "content": record.get("content", ""),
                            "memory_type": record.get("memory_type", "conversation"),
                            "created_at": str(record.get("created_at", "")) if record.get("created_at") else "",
                            "metadata": metadata,
                            "mentioned_user_id": record.get("mentioned_user_id"),
                            "score": score
                        })
                    
                    # Re-sort by boosted score
                    memories.sort(key=lambda x: x["score"], reverse=True)
                    return memories[:top_k]
                except:
                    self.use_vector_index = False
            
            # Fallback: Manual cosine similarity
            cypher = """
                MATCH (c:Channel {id: $channel_id})-[:HAS_MEMORY]->(m:Memory)
                WHERE m.embedding IS NOT NULL
            """
            params = {"channel_id": channel_id}
            
            if memory_types:
                cypher += " AND m.memory_type IN $memory_types"
                params["memory_types"] = memory_types
            
            cypher += """
                RETURN m.content AS content,
                       m.memory_type AS memory_type,
                       toString(m.created_at) AS created_at,
                       COALESCE(m.metadata, "{}") AS metadata,
                       m.embedding AS embedding,
                       m.mentioned_user_id AS mentioned_user_id
            """
            
            result = session.run(cypher, **params)
            
            # Batch process for speed
            records = list(result)
            if not records:
                return []
            
            # Vectorized cosine similarity calculation
            query_vec = np.array(query_embedding, dtype=np.float32)
            memory_embeddings = np.array([record["embedding"] for record in records], dtype=np.float32)
            
            # Normalize query vector once
            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                query_norm = 1.0
            
            # Compute dot products (vectorized)
            dot_products = np.dot(memory_embeddings, query_vec)
            
            # Compute norms (vectorized)
            memory_norms = np.linalg.norm(memory_embeddings, axis=1)
            memory_norms = np.where(memory_norms == 0, 1.0, memory_norms)
            
            # Cosine similarity (vectorized)
            similarities_scores = dot_products / (memory_norms * query_norm)
            
            # Create results with scores
            similarities = []
            for i, record in enumerate(records):
                metadata_str = record.get("metadata", "{}")
                try:
                    metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else (metadata_str or {})
                except:
                    metadata = {}
                
                score = float(similarities_scores[i])
                # Boost score if this memory mentions the queried user
                if mentioned_user_id and record.get("mentioned_user_id") == mentioned_user_id:
                    score = score * 1.2
                
                similarities.append({
                    "content": record.get("content", ""),
                    "memory_type": record.get("memory_type", "conversation"),
                    "created_at": str(record.get("created_at", "")) if record.get("created_at") else "",
                    "metadata": metadata,
                    "mentioned_user_id": record.get("mentioned_user_id"),
                    "score": score
                })
            
            # Sort by boosted similarity score and return top_k
            similarities.sort(key=lambda x: x["score"], reverse=True)
            return similarities[:top_k]
    
    def get_channel_memories(self, channel_id: str = None, channel_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all memories for a channel (for admin view).
        Can search by channel_id or channel_name.
        """
        with self.driver.session() as session:
            # Build query based on what identifier is provided
            if channel_id:
                # Direct lookup by channel ID (most efficient)
                result = session.run("""
                    MATCH (c:Channel {id: $channel_id})-[:HAS_MEMORY]->(m:Memory)
                    RETURN m.content AS content,
                           m.memory_type AS memory_type,
                           toString(m.created_at) AS created_at,
                           COALESCE(m.metadata, "{}") AS metadata
                    ORDER BY m.created_at DESC
                    LIMIT $limit
                """, channel_id=channel_id, limit=limit)
            elif channel_name:
                # Lookup by channel name
                result = session.run("""
                    MATCH (c:Channel {name: $channel_name})-[:HAS_MEMORY]->(m:Memory)
                    RETURN m.content AS content,
                           m.memory_type AS memory_type,
                           toString(m.created_at) AS created_at,
                           COALESCE(m.metadata, "{}") AS metadata
                    ORDER BY m.created_at DESC
                    LIMIT $limit
                """, channel_name=channel_name, limit=limit)
            else:
                return []
            
            memories = []
            for record in result:
                metadata_str = record.get('metadata', '{}')
                try:
                    metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else (metadata_str or {})
                except:
                    metadata = {}
                memory = {
                    'content': record.get('content', ''),
                    'memory_type': record.get('memory_type', 'conversation'),
                    'created_at': record.get('created_at', ''),
                    'metadata': metadata
                }
                memories.append(memory)
            
            return memories
    
    def get_all_channels(self) -> List[Dict[str, Any]]:
        """Get all channels with memory counts (for admin)."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Channel)
                OPTIONAL MATCH (c)-[:HAS_MEMORY]->(m:Memory)
                RETURN c.id AS channel_id,
                       c.name AS channel_name,
                       toString(c.last_active) AS last_active,
                       count(m) AS memory_count
                ORDER BY memory_count DESC
            """)
            
            channels = []
            for record in result:
                channel = {
                    'channel_id': record.get('channel_id', ''),
                    'channel_name': record.get('channel_name', 'Unknown'),
                    'last_active': record.get('last_active', ''),
                    'memory_count': record.get('memory_count', 0)
                }
                channels.append(channel)
            
            return channels
    
    def get_all_memories(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all memories across all channels (for admin view)."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Channel)-[:HAS_MEMORY]->(m:Memory)
                RETURN m.content AS content,
                       m.memory_type AS memory_type,
                       toString(m.created_at) AS created_at,
                       COALESCE(m.metadata, "{}") AS metadata,
                       c.id AS channel_id,
                       c.name AS channel_name
                ORDER BY m.created_at DESC
                LIMIT $limit
            """, limit=limit)
            
            memories = []
            for record in result:
                metadata_str = record.get('metadata', '{}')
                try:
                    metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else (metadata_str or {})
                except:
                    metadata = {}
                memory = {
                    'content': record.get('content', ''),
                    'memory_type': record.get('memory_type', 'conversation'),
                    'created_at': record.get('created_at', ''),
                    'metadata': metadata,
                    'channel_id': record.get('channel_id', ''),
                    'channel_name': record.get('channel_name', 'Unknown')
                }
                memories.append(memory)
            
            return memories
    
    def delete_memory(self, memory_id: str):
        """Delete a memory."""
        with self.driver.session() as session:
            session.run("""
                MATCH (m:Memory {id: $memory_id})
                DETACH DELETE m
            """, memory_id=memory_id)
    
    def close(self):
        """Close connection."""
        self.driver.close()

