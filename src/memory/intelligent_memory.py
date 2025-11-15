"""
Intelligent memory management system with:
- Memory consolidation and summarization
- Importance scoring
- Automatic forgetting/archiving
- Memory clustering and deduplication
- Context-aware memory retrieval
"""
from typing import List, Dict, Any, Optional, Tuple
from neo4j import GraphDatabase
import json
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBEDDING_DIMENSION
from config import ELASTICSEARCH_ENABLED
from logger_config import logger

# Try to use hybrid memory store if Elasticsearch is enabled
try:
    from src.stores.hybrid_memory_store import HybridMemoryStore
    HYBRID_MEMORY_AVAILABLE = True
except ImportError:
    HYBRID_MEMORY_AVAILABLE = False

from src.stores.memory_store import MemoryStore


class IntelligentMemory:
    """
    Advanced memory management system that:
    - Scores memories by importance
    - Consolidates similar memories
    - Automatically archives old/unimportant memories
    - Clusters related memories
    - Provides context-aware retrieval
    - Uses Elasticsearch for faster search if enabled
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD, memory_store=None):
        """Initialize intelligent memory system."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
        # Use provided memory store if available, otherwise create new one
        if memory_store is not None:
            self.memory_store = memory_store
        elif ELASTICSEARCH_ENABLED and HYBRID_MEMORY_AVAILABLE:
            try:
                self.memory_store = HybridMemoryStore()
                logger.info("✅ Using HybridMemoryStore (Neo4j + Elasticsearch)")
            except Exception as e:
                logger.warning(f"Failed to initialize HybridMemoryStore, using regular MemoryStore: {e}")
                self.memory_store = MemoryStore(uri, user, password)
        else:
            self.memory_store = MemoryStore(uri, user, password)
        
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize intelligent memory schema."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE")
                session.run("CREATE INDEX memory_importance IF NOT EXISTS FOR (m:Memory) ON (m.importance_score)")
                session.run("CREATE INDEX memory_created IF NOT EXISTS FOR (m:Memory) ON (m.created_at)")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def score_memory_importance(self,
                               memory_id: str,
                               factors: Dict[str, float] = None) -> float:
        """
        Score memory importance based on multiple factors:
        - Recency (recent memories are more important)
        - Frequency (frequently accessed memories)
        - User mentions (memories mentioning users)
        - Query relevance (how often it's retrieved)
        - Memory type (facts > conversations)
        
        Args:
            memory_id: Memory ID to score
            factors: Optional custom weights for factors
            
        Returns:
            Importance score (0.0 to 1.0)
        """
        default_factors = {
            "recency": 0.3,
            "frequency": 0.25,
            "user_mentions": 0.2,
            "query_relevance": 0.15,
            "memory_type": 0.1
        }
        
        if factors:
            default_factors.update(factors)
        
        factors = default_factors
        
        with self.driver.session() as session:
            # Removed MENTIONED_IN relationship to avoid Neo4j warnings when it doesn't exist yet
            # The relationship is optional and will be created when users are mentioned in memories
            result = session.run("""
                MATCH (m:Memory {id: $memory_id})
                RETURN m.created_at AS created_at,
                       m.memory_type AS memory_type,
                       m.access_count AS access_count,
                       m.last_accessed AS last_accessed,
                       0 AS mention_count,
                       m.importance_score AS current_score
            """,
                memory_id=memory_id
            )
            
            record = result.single()
            if not record:
                return 0.0
            
            # Recency score (0-1, decays over time)
            created_at = record.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        created_dt = created_at
                    
                    age_days = (datetime.now(created_dt.tzinfo) - created_dt).days
                    recency_score = max(0.0, 1.0 - (age_days / 90.0))  # Decay over 90 days
                except:
                    recency_score = 0.5
            else:
                recency_score = 0.5
            
            # Frequency score (based on access count)
            access_count = record.get("access_count", 0)
            frequency_score = min(1.0, access_count / 10.0)  # Normalize to 0-1
            
            # User mentions score
            mention_count = record.get("mention_count", 0)
            user_mentions_score = min(1.0, mention_count / 3.0)  # Normalize to 0-1
            
            # Query relevance (stored in memory, defaults to 0.5)
            query_relevance = record.get("query_relevance", 0.5)
            
            # Memory type score
            memory_type = record.get("memory_type", "conversation")
            type_scores = {
                "fact": 1.0,
                "preference": 0.9,
                "expertise": 0.8,
                "bot_response": 0.7,
                "conversation": 0.5,
                "temporary": 0.2
            }
            memory_type_score = type_scores.get(memory_type, 0.5)
            
            # Calculate weighted importance score
            importance = (
                factors["recency"] * recency_score +
                factors["frequency"] * frequency_score +
                factors["user_mentions"] * user_mentions_score +
                factors["query_relevance"] * query_relevance +
                factors["memory_type"] * memory_type_score
            )
            
            # Update memory with importance score
            session.run("""
                MATCH (m:Memory {id: $memory_id})
                SET m.importance_score = $importance,
                    m.last_scored = datetime()
            """,
                memory_id=memory_id,
                importance=importance
            )
            
            return importance
    
    def consolidate_similar_memories(self,
                                     channel_id: str,
                                     similarity_threshold: float = 0.85,
                                     max_age_days: int = 7) -> List[Dict[str, Any]]:
        """
        Find and consolidate similar memories.
        Groups memories with high semantic similarity and creates summaries.
        
        Returns:
            List of consolidation operations performed
        """
        consolidations = []
        
        with self.driver.session() as session:
            # Get recent memories for the channel
            result = session.run("""
                MATCH (c:Channel {id: $channel_id})-[:HAS_MEMORY]->(m:Memory)
                WHERE m.created_at > datetime() - duration({days: $max_age_days})
                    AND m.consolidated = false OR m.consolidated IS NULL
                RETURN m.id AS memory_id,
                       m.content AS content,
                       m.embedding AS embedding,
                       m.memory_type AS memory_type,
                       m.created_at AS created_at
                ORDER BY m.created_at DESC
            """,
                channel_id=channel_id,
                max_age_days=max_age_days
            )
            
            memories = list(result)
            if len(memories) < 2:
                return consolidations
            
            # Group similar memories
            memory_groups = []
            processed = set()
            
            for i, mem1 in enumerate(memories):
                if mem1["memory_id"] in processed:
                    continue
                
                group = [mem1]
                processed.add(mem1["memory_id"])
                
                mem1_embedding = mem1["embedding"]
                if not mem1_embedding:
                    continue
                
                for j, mem2 in enumerate(memories[i+1:], start=i+1):
                    if mem2["memory_id"] in processed:
                        continue
                    
                    mem2_embedding = mem2["embedding"]
                    if not mem2_embedding:
                        continue
                    
                    # Calculate cosine similarity
                    similarity = self._cosine_similarity(mem1_embedding, mem2_embedding)
                    
                    if similarity >= similarity_threshold:
                        group.append(mem2)
                        processed.add(mem2["memory_id"])
                
                if len(group) > 1:
                    memory_groups.append(group)
            
            # Consolidate each group
            for group in memory_groups:
                consolidation = self._consolidate_group(group, channel_id)
                if consolidation:
                    consolidations.append(consolidation)
            
            return consolidations
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        vec1_arr = np.array(vec1, dtype=np.float32)
        vec2_arr = np.array(vec2, dtype=np.float32)
        
        dot_product = np.dot(vec1_arr, vec2_arr)
        norm1 = np.linalg.norm(vec1_arr)
        norm2 = np.linalg.norm(vec2_arr)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def _consolidate_group(self,
                          memory_group: List[Dict[str, Any]],
                          channel_id: str) -> Optional[Dict[str, Any]]:
        """Consolidate a group of similar memories into one."""
        if len(memory_group) < 2:
            return None
        
        # Sort by importance (most important first)
        memory_group.sort(key=lambda m: m.get("importance_score", 0), reverse=True)
        
        # Create consolidated content (combine unique information)
        contents = [m["content"] for m in memory_group]
        consolidated_content = self._merge_memory_contents(contents)
        
        # Use embedding from most important memory
        primary_memory = memory_group[0]
        consolidated_embedding = primary_memory["embedding"]
        
        # Mark original memories as consolidated
        memory_ids = [m["memory_id"] for m in memory_group]
        
        with self.driver.session() as session:
            # Create consolidated memory
            consolidated_id = f"consolidated_{channel_id}_{datetime.now().timestamp()}"
            
            session.run("""
                CREATE (m:Memory {
                    id: $memory_id,
                    channel_id: $channel_id,
                    content: $content,
                    memory_type: $memory_type,
                    embedding: $embedding,
                    created_at: datetime(),
                    consolidated: true,
                    source_memories: $source_memories
                })
                WITH m
                MATCH (c:Channel {id: $channel_id})
                CREATE (c)-[:HAS_MEMORY]->(m)
            """,
                memory_id=consolidated_id,
                channel_id=channel_id,
                content=consolidated_content,
                memory_type=primary_memory["memory_type"],
                embedding=consolidated_embedding,
                source_memories=json.dumps(memory_ids)
            )
            
            # Mark original memories as consolidated
            for mem_id in memory_ids:
                session.run("""
                    MATCH (m:Memory {id: $memory_id})
                    SET m.consolidated = true,
                        m.consolidated_into = $consolidated_id
                """,
                    memory_id=mem_id,
                    consolidated_id=consolidated_id
                )
        
        return {
            "consolidated_id": consolidated_id,
            "source_memories": memory_ids,
            "count": len(memory_group)
        }
    
    def _merge_memory_contents(self, contents: List[str]) -> str:
        """
        Merge multiple memory contents intelligently.
        Removes duplicates and combines unique information.
        """
        # Simple deduplication - can be enhanced with LLM summarization
        unique_sentences = set()
        
        for content in contents:
            sentences = content.split('. ')
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and len(sentence) > 10:  # Filter very short sentences
                    unique_sentences.add(sentence)
        
        merged = '. '.join(sorted(unique_sentences))
        return merged[:2000]  # Limit length
    
    def archive_old_memories(self,
                            channel_id: str,
                            max_age_days: int = 90,
                            min_importance: float = 0.2) -> int:
        """
        Archive old, low-importance memories.
        Archived memories are not deleted but marked for reduced retrieval priority.
        
        Returns:
            Number of memories archived
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Channel {id: $channel_id})-[:HAS_MEMORY]->(m:Memory)
                WHERE m.created_at < datetime() - duration({days: $max_age_days})
                    AND (m.importance_score < $min_importance OR m.importance_score IS NULL)
                    AND (m.archived = false OR m.archived IS NULL)
                SET m.archived = true,
                    m.archived_at = datetime()
                RETURN count(m) AS archived_count
            """,
                channel_id=channel_id,
                max_age_days=max_age_days,
                min_importance=min_importance
            )
            
            record = result.single()
            return record.get("archived_count", 0) if record else 0
    
    def retrieve_with_context(self,
                             channel_id: str,
                             query_embedding: List[float],
                             top_k: int = 5,
                             include_archived: bool = False,
                             min_importance: float = 0.0) -> List[Dict[str, Any]]:
        """
        Retrieve memories with context-aware filtering.
        Considers importance scores and recency.
        """
        memories = self.memory_store.retrieve_relevant_memories(
            channel_id, query_embedding, top_k * 2  # Get more to filter
        )
        
        # Filter by importance and archived status
        filtered = []
        for memory in memories:
            # Skip archived unless requested
            if not include_archived and memory.get("archived", False):
                continue
            
            # Score importance if not already scored
            memory_id = memory.get("id")
            if memory_id:
                importance = self.score_memory_importance(memory_id)
                memory["importance_score"] = importance
            else:
                importance = memory.get("importance_score", 0.5)
            
            # Filter by minimum importance
            if importance >= min_importance:
                # Boost score by importance
                original_score = memory.get("score", 0)
                memory["score"] = original_score * (0.7 + 0.3 * importance)
                filtered.append(memory)
        
        # Sort by combined score and return top_k
        filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
        return filtered[:top_k]
    
    def track_memory_access(self, memory_id: str):
        """Track when a memory is accessed (for frequency scoring)."""
        with self.driver.session() as session:
            session.run("""
                MATCH (m:Memory {id: $memory_id})
                SET m.access_count = COALESCE(m.access_count, 0) + 1,
                    m.last_accessed = datetime()
            """,
                memory_id=memory_id
            )
    
    def update_memory_relevance(self, memory_id: str, relevance_score: float):
        """Update memory query relevance score."""
        with self.driver.session() as session:
            session.run("""
                MATCH (m:Memory {id: $memory_id})
                SET m.query_relevance = $relevance_score
            """,
                memory_id=memory_id,
                relevance_score=relevance_score
            )
    
    def close(self):
        """Close connections."""
        self.driver.close()
        self.memory_store.close()

