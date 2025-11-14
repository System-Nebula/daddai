"""
Advanced user relations system with profiles, preferences, relationships, and context tracking.
Leverages Neo4j graph database for rich relationship modeling.
"""
from typing import List, Dict, Any, Optional, Set
from neo4j import GraphDatabase
import json
from datetime import datetime, timedelta
from collections import defaultdict
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger


class UserRelations:
    """
    Advanced user relations system tracking:
    - User profiles and preferences
    - User relationships (mentions, interactions, collaborations)
    - User expertise and interests
    - Cross-user context awareness
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize user relations store."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize user relations schema in Neo4j."""
        with self.driver.session() as session:
            try:
                # User constraints
                session.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
                
                # Create indexes for faster queries
                session.run("CREATE INDEX user_username IF NOT EXISTS FOR (u:User) ON (u.username)")
                session.run("CREATE INDEX user_last_active IF NOT EXISTS FOR (u:User) ON (u.last_active)")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def create_or_update_user(self,
                              user_id: str,
                              username: str = None,
                              preferences: Dict[str, Any] = None,
                              metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create or update user profile.
        
        Args:
            user_id: Unique user identifier
            username: Username/display name
            preferences: User preferences (response style, topics, etc.)
            metadata: Additional metadata
            
        Returns:
            User profile dictionary
        """
        with self.driver.session() as session:
            preferences_json = json.dumps(preferences) if preferences else "{}"
            metadata_json = json.dumps(metadata) if metadata else "{}"
            
            session.run("""
                MERGE (u:User {id: $user_id})
                SET u.username = COALESCE($username, u.username),
                    u.preferences = $preferences_json,
                    u.metadata = $metadata_json,
                    u.last_active = datetime(),
                    u.created_at = COALESCE(u.created_at, datetime())
            """,
                user_id=user_id,
                username=username,
                preferences_json=preferences_json,
                metadata_json=metadata_json
            )
            
            return self.get_user_profile(user_id)
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile with aggregated statistics."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})
                OPTIONAL MATCH (u)-[:MENTIONED_IN]->(m:Memory)
                OPTIONAL MATCH (u)-[:UPLOADED]->(d:SharedDocument)
                OPTIONAL MATCH (u)-[:INTERACTS_WITH]->(other:User)
                RETURN u.id AS id,
                       u.username AS username,
                       u.preferences AS preferences,
                       u.metadata AS metadata,
                       toString(u.last_active) AS last_active,
                       toString(u.created_at) AS created_at,
                       count(DISTINCT m) AS memory_count,
                       count(DISTINCT d) AS document_count,
                       count(DISTINCT other) AS interaction_count
            """, user_id=user_id)
            
            record = result.single()
            if not record:
                return {}
            
            preferences_str = record.get("preferences", "{}")
            metadata_str = record.get("metadata", "{}")
            
            try:
                preferences = json.loads(preferences_str) if isinstance(preferences_str, str) else (preferences_str or {})
            except:
                preferences = {}
            
            try:
                metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else (metadata_str or {})
            except:
                metadata = {}
            
            return {
                "id": record.get("id"),
                "username": record.get("username"),
                "preferences": preferences,
                "metadata": metadata,
                "last_active": record.get("last_active"),
                "created_at": record.get("created_at"),
                "statistics": {
                    "memory_count": record.get("memory_count", 0),
                    "document_count": record.get("document_count", 0),
                    "interaction_count": record.get("interaction_count", 0)
                }
            }
    
    def track_user_mention(self,
                          user_id: str,
                          mentioned_user_id: str,
                          context: str,
                          channel_id: str,
                          memory_id: str = None):
        """
        Track when one user mentions another user.
        Creates relationship and updates interaction strength.
        """
        with self.driver.session() as session:
            # Create both user nodes if they don't exist
            session.run("MERGE (u1:User {id: $user_id})", user_id=user_id)
            session.run("MERGE (u2:User {id: $mentioned_user_id})", mentioned_user_id=mentioned_user_id)
            
            # Create or update INTERACTS_WITH relationship
            session.run("""
                MATCH (u1:User {id: $user_id})
                MATCH (u2:User {id: $mentioned_user_id})
                MERGE (u1)-[r:INTERACTS_WITH]->(u2)
                SET r.strength = COALESCE(r.strength, 0) + 1,
                    r.last_interaction = datetime(),
                    r.total_interactions = COALESCE(r.total_interactions, 0) + 1
            """,
                user_id=user_id,
                mentioned_user_id=mentioned_user_id
            )
            
            # Link to memory if provided
            if memory_id:
                session.run("""
                    MATCH (u:User {id: $mentioned_user_id})
                    MATCH (m:Memory {id: $memory_id})
                    MERGE (u)-[:MENTIONED_IN]->(m)
                """,
                    mentioned_user_id=mentioned_user_id,
                    memory_id=memory_id
                )
    
    def get_user_relationships(self, user_id: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get user's relationships sorted by interaction strength.
        
        Returns:
            List of related users with interaction metrics
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})-[r:INTERACTS_WITH]->(other:User)
                RETURN other.id AS user_id,
                       other.username AS username,
                       r.strength AS strength,
                       toString(r.last_interaction) AS last_interaction,
                       r.total_interactions AS total_interactions
                ORDER BY r.strength DESC, r.last_interaction DESC
                LIMIT $top_n
            """,
                user_id=user_id,
                top_n=top_n
            )
            
            relationships = []
            for record in result:
                relationships.append({
                    "user_id": record.get("user_id"),
                    "username": record.get("username"),
                    "strength": record.get("strength", 0),
                    "last_interaction": record.get("last_interaction"),
                    "total_interactions": record.get("total_interactions", 0)
                })
            
            return relationships
    
    def track_user_expertise(self,
                            user_id: str,
                            topic: str,
                            confidence: float = 1.0,
                            source: str = "inferred"):
        """
        Track user expertise in specific topics.
        Useful for routing questions to experts or providing context.
        """
        with self.driver.session() as session:
            session.run("MERGE (u:User {id: $user_id})", user_id=user_id)
            
            session.run("""
                MATCH (u:User {id: $user_id})
                MERGE (t:Topic {name: $topic})
                MERGE (u)-[e:EXPERT_IN]->(t)
                SET e.confidence = COALESCE(e.confidence, 0) + $confidence,
                    e.last_updated = datetime(),
                    e.source = $source
            """,
                user_id=user_id,
                topic=topic.lower(),
                confidence=confidence,
                source=source
            )
    
    def get_experts_for_topic(self, topic: str, min_confidence: float = 0.5) -> List[Dict[str, Any]]:
        """
        Find users who are experts in a given topic.
        
        Returns:
            List of expert users sorted by confidence
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User)-[e:EXPERT_IN]->(t:Topic {name: $topic})
                WHERE e.confidence >= $min_confidence
                RETURN u.id AS user_id,
                       u.username AS username,
                       e.confidence AS confidence,
                       toString(e.last_updated) AS last_updated
                ORDER BY e.confidence DESC
            """,
                topic=topic.lower(),
                min_confidence=min_confidence
            )
            
            experts = []
            for record in result:
                experts.append({
                    "user_id": record.get("user_id"),
                    "username": record.get("username"),
                    "confidence": record.get("confidence", 0),
                    "last_updated": record.get("last_updated")
                })
            
            return experts
    
    def track_user_interests(self,
                            user_id: str,
                            interests: List[str],
                            source: str = "inferred"):
        """
        Track user interests based on queries, document uploads, etc.
        """
        with self.driver.session() as session:
            session.run("MERGE (u:User {id: $user_id})", user_id=user_id)
            
            for interest in interests:
                session.run("""
                    MATCH (u:User {id: $user_id})
                    MERGE (i:Interest {name: $interest})
                    MERGE (u)-[r:INTERESTED_IN]->(i)
                    SET r.strength = COALESCE(r.strength, 0) + 1,
                        r.last_updated = datetime(),
                        r.source = $source
                """,
                    user_id=user_id,
                    interest=interest.lower(),
                    source=source
                )
    
    def get_user_interests(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user's interests sorted by strength."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})-[r:INTERESTED_IN]->(i:Interest)
                RETURN i.name AS interest,
                       r.strength AS strength,
                       toString(r.last_updated) AS last_updated
                ORDER BY r.strength DESC
            """,
                user_id=user_id
            )
            
            interests = []
            for record in result:
                interests.append({
                    "interest": record.get("interest"),
                    "strength": record.get("strength", 0),
                    "last_updated": record.get("last_updated")
                })
            
            return interests
    
    def get_contextual_users(self,
                            query: str,
                            channel_id: str,
                            top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Get users who are contextually relevant to a query.
        Considers:
        - Users mentioned in recent memories
        - Users with expertise in query topics
        - Users with interests matching the query
        - Users who uploaded relevant documents
        """
        # Extract potential topics/interests from query (simple keyword extraction)
        query_lower = query.lower()
        potential_topics = [word for word in query_lower.split() if len(word) > 4]
        
        relevant_users = set()
        user_scores = defaultdict(float)
        
        with self.driver.session() as session:
            # Find users mentioned in recent channel memories
            result = session.run("""
                MATCH (c:Channel {id: $channel_id})-[:HAS_MEMORY]->(m:Memory)
                WHERE m.created_at > datetime() - duration({days: 7})
                MATCH (u:User)-[:MENTIONED_IN]->(m)
                RETURN DISTINCT u.id AS user_id, u.username AS username
            """,
                channel_id=channel_id
            )
            
            for record in result:
                user_id = record.get("user_id")
                relevant_users.add(user_id)
                user_scores[user_id] += 2.0  # High weight for recent mentions
            
            # Find users with expertise in query topics
            for topic in potential_topics[:5]:  # Limit to top 5 topics
                result = session.run("""
                    MATCH (u:User)-[e:EXPERT_IN]->(t:Topic)
                    WHERE t.name CONTAINS $topic
                    RETURN u.id AS user_id, e.confidence AS confidence
                """,
                    topic=topic
                )
                
                for record in result:
                    user_id = record.get("user_id")
                    confidence = record.get("confidence", 0)
                    relevant_users.add(user_id)
                    user_scores[user_id] += confidence * 1.5
            
            # Find users with matching interests
            for topic in potential_topics[:5]:
                result = session.run("""
                    MATCH (u:User)-[r:INTERESTED_IN]->(i:Interest)
                    WHERE i.name CONTAINS $topic
                    RETURN u.id AS user_id, r.strength AS strength
                """,
                    topic=topic
                )
                
                for record in result:
                    user_id = record.get("user_id")
                    strength = record.get("strength", 0)
                    relevant_users.add(user_id)
                    user_scores[user_id] += strength * 0.5
        
        # Sort by score and return top_n
        sorted_users = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        
        # Get full user profiles
        contextual_users = []
        for user_id, score in sorted_users:
            profile = self.get_user_profile(user_id)
            if profile:
                profile["relevance_score"] = score
                contextual_users.append(profile)
        
        return contextual_users
    
    def update_user_preferences(self,
                               user_id: str,
                               preferences: Dict[str, Any]):
        """Update user preferences."""
        with self.driver.session() as session:
            preferences_json = json.dumps(preferences)
            session.run("""
                MATCH (u:User {id: $user_id})
                SET u.preferences = $preferences_json,
                    u.last_active = datetime()
            """,
                user_id=user_id,
                preferences_json=preferences_json
            )
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user preferences."""
        profile = self.get_user_profile(user_id)
        return profile.get("preferences", {})
    
    def close(self):
        """Close connection."""
        self.driver.close()

