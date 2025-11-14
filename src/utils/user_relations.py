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
                
                # Persona constraints (multiple personas per user_id)
                session.run("CREATE CONSTRAINT persona_id IF NOT EXISTS FOR (p:Persona) REQUIRE p.id IS UNIQUE")
                
                # Create indexes for faster queries
                session.run("CREATE INDEX user_username IF NOT EXISTS FOR (u:User) ON (u.username)")
                session.run("CREATE INDEX user_last_active IF NOT EXISTS FOR (u:User) ON (u.last_active)")
                session.run("CREATE INDEX persona_name IF NOT EXISTS FOR (p:Persona) ON (p.name)")
                session.run("CREATE INDEX persona_user IF NOT EXISTS FOR (p:Persona) ON (p.user_id)")
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
            # Removed MENTIONED_IN relationship to avoid Neo4j warnings when it doesn't exist yet
            # The relationship is optional and will be created when users are mentioned in memories
            result = session.run("""
                MATCH (u:User {id: $user_id})
                OPTIONAL MATCH (u)-[:UPLOADED]->(d:SharedDocument)
                OPTIONAL MATCH (u)-[:INTERACTS_WITH]->(other:User)
                RETURN u.id AS id,
                       u.username AS username,
                       COALESCE(u.preferences, "{}") AS preferences,
                       COALESCE(u.metadata, "{}") AS metadata,
                       toString(COALESCE(u.last_active, datetime())) AS last_active,
                       toString(COALESCE(u.created_at, datetime())) AS created_at,
                       0 AS memory_count,
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
            # Use OPTIONAL MATCH to avoid warnings when relationships don't exist yet
            result = session.run("""
                MATCH (u:User {id: $user_id})
                OPTIONAL MATCH (u)-[r:INTERACTS_WITH]->(other:User)
                WHERE r IS NOT NULL AND other IS NOT NULL
                RETURN other.id AS user_id,
                       other.username AS username,
                       COALESCE(r.strength, 0) AS strength,
                       toString(COALESCE(r.last_interaction, datetime())) AS last_interaction,
                       COALESCE(r.total_interactions, 0) AS total_interactions
                ORDER BY COALESCE(r.strength, 0) DESC, COALESCE(r.last_interaction, datetime('1970-01-01')) DESC
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
            # Find users mentioned in recent channel memories (OPTIONAL MATCH to avoid warnings)
            result = session.run("""
                MATCH (c:Channel {id: $channel_id})-[:HAS_MEMORY]->(m:Memory)
                WHERE m.created_at > datetime() - duration({days: 7})
                OPTIONAL MATCH (u:User)-[:MENTIONED_IN]->(m)
                WHERE u IS NOT NULL
                RETURN DISTINCT u.id AS user_id, u.username AS username
            """,
                channel_id=channel_id
            )
            
            for record in result:
                user_id = record.get("user_id")
                if user_id:  # Only process if user_id exists
                    relevant_users.add(user_id)
                    user_scores[user_id] += 2.0  # High weight for recent mentions
            
            # Find users with expertise in query topics (OPTIONAL MATCH to avoid warnings)
            for topic in potential_topics[:5]:  # Limit to top 5 topics
                result = session.run("""
                    OPTIONAL MATCH (u:User)-[e:EXPERT_IN]->(t:Topic)
                    WHERE t.name CONTAINS $topic AND u IS NOT NULL
                    RETURN u.id AS user_id, COALESCE(e.confidence, 0) AS confidence
                """,
                    topic=topic
                )
                
                for record in result:
                    user_id = record.get("user_id")
                    if user_id:  # Only process if user_id exists
                        confidence = record.get("confidence", 0)
                        relevant_users.add(user_id)
                        user_scores[user_id] += confidence * 1.5
            
            # Find users with matching interests (OPTIONAL MATCH to avoid warnings)
            for topic in potential_topics[:5]:
                result = session.run("""
                    OPTIONAL MATCH (u:User)-[r:INTERESTED_IN]->(i:Interest)
                    WHERE i.name CONTAINS $topic AND u IS NOT NULL
                    RETURN u.id AS user_id, COALESCE(r.strength, 0) AS strength
                """,
                    topic=topic
                )
                
                for record in result:
                    user_id = record.get("user_id")
                    if user_id:  # Only process if user_id exists
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
    
    def create_or_update_persona(self,
                                user_id: str,
                                persona_name: str,
                                persona_id: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create or update a persona (identity) for a user.
        Each user_id can have multiple personas (different people talking to the bot).
        
        Args:
            user_id: User ID (Discord user ID, etc.)
            persona_name: Name/identifier for this persona (e.g., "Alice", "Bob", "Work Persona")
            persona_id: Optional unique persona ID (auto-generated if not provided)
            metadata: Persona-specific metadata (preferences, context, etc.)
            
        Returns:
            Persona ID
        """
        if not persona_id:
            persona_id = f"{user_id}_{persona_name}_{datetime.now().timestamp()}"
        
        with self.driver.session() as session:
            # Ensure user exists
            session.run("MERGE (u:User {id: $user_id})", user_id=user_id)
            
            metadata_json = json.dumps(metadata) if metadata else "{}"
            
            # Create or update persona
            session.run("""
                MERGE (p:Persona {id: $persona_id})
                SET p.name = $persona_name,
                    p.user_id = $user_id,
                    p.metadata = $metadata_json,
                    p.last_active = datetime(),
                    p.created_at = COALESCE(p.created_at, datetime())
                WITH p
                MATCH (u:User {id: $user_id})
                MERGE (u)-[:HAS_PERSONA]->(p)
            """,
                persona_id=persona_id,
                persona_name=persona_name,
                user_id=user_id,
                metadata_json=metadata_json
            )
        
        logger.debug(f"Created/updated persona {persona_name} for user {user_id}")
        return persona_id
    
    def get_personas_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all personas for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of persona dictionaries
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})-[:HAS_PERSONA]->(p:Persona)
                RETURN p.id AS id,
                       p.name AS name,
                       p.metadata AS metadata,
                       toString(p.last_active) AS last_active,
                       toString(p.created_at) AS created_at
                ORDER BY p.last_active DESC
            """,
                user_id=user_id
            )
            
            personas = []
            for record in result:
                metadata_str = record.get("metadata", "{}")
                try:
                    metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else (metadata_str or {})
                except:
                    metadata = {}
                
                personas.append({
                    "id": record.get("id"),
                    "name": record.get("name"),
                    "metadata": metadata,
                    "last_active": record.get("last_active"),
                    "created_at": record.get("created_at")
                })
            
            return personas
    
    def track_persona_interaction(self,
                                 persona_id_1: str,
                                 persona_id_2: str,
                                 interaction_type: str = "mentioned",
                                 context: Optional[str] = None,
                                 channel_id: Optional[str] = None):
        """
        Track interaction between two personas.
        This tracks relationships between different people (personas) talking to the bot.
        
        Args:
            persona_id_1: First persona ID
            persona_id_2: Second persona ID
            interaction_type: Type of interaction (mentioned, collaborated, etc.)
            context: Context of the interaction
            channel_id: Channel where interaction occurred
        """
        with self.driver.session() as session:
            # Ensure personas exist
            session.run("MERGE (p1:Persona {id: $persona_id_1})", persona_id_1=persona_id_1)
            session.run("MERGE (p2:Persona {id: $persona_id_2})", persona_id_2=persona_id_2)
            
            # Create or update interaction relationship
            session.run("""
                MATCH (p1:Persona {id: $persona_id_1})
                MATCH (p2:Persona {id: $persona_id_2})
                MERGE (p1)-[r:INTERACTS_WITH_PERSONA]->(p2)
                SET r.interaction_type = $interaction_type,
                    r.strength = COALESCE(r.strength, 0) + 1,
                    r.last_interaction = datetime(),
                    r.total_interactions = COALESCE(r.total_interactions, 0) + 1,
                    r.context = COALESCE(r.context, []) + [$context],
                    r.channel_id = $channel_id
            """,
                persona_id_1=persona_id_1,
                persona_id_2=persona_id_2,
                interaction_type=interaction_type,
                context=context,
                channel_id=channel_id
            )
    
    def get_persona_relationships(self, persona_id: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get relationships for a persona (relationships with other personas).
        
        Args:
            persona_id: Persona ID
            top_n: Number of relationships to return
            
        Returns:
            List of related personas with interaction metrics
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p1:Persona {id: $persona_id})-[r:INTERACTS_WITH_PERSONA]->(p2:Persona)
                RETURN p2.id AS persona_id,
                       p2.name AS persona_name,
                       p2.user_id AS user_id,
                       r.interaction_type AS interaction_type,
                       r.strength AS strength,
                       toString(r.last_interaction) AS last_interaction,
                       r.total_interactions AS total_interactions
                ORDER BY r.strength DESC, r.last_interaction DESC
                LIMIT $top_n
            """,
                persona_id=persona_id,
                top_n=top_n
            )
            
            relationships = []
            for record in result:
                relationships.append({
                    "persona_id": record.get("persona_id"),
                    "persona_name": record.get("persona_name"),
                    "user_id": record.get("user_id"),
                    "interaction_type": record.get("interaction_type"),
                    "strength": record.get("strength", 0),
                    "last_interaction": record.get("last_interaction"),
                    "total_interactions": record.get("total_interactions", 0)
                })
            
            return relationships
    
    def identify_active_persona(self,
                               user_id: str,
                               message_text: str,
                               channel_id: Optional[str] = None,
                               username: Optional[str] = None) -> Optional[str]:
        """
        Identify which persona is currently speaking based on context.
        Uses heuristics and LLM to determine persona identity.
        
        Args:
            user_id: User ID
            message_text: Message text
            channel_id: Channel ID
            username: Username
            
        Returns:
            Persona ID if identified, None otherwise
        """
        # Get existing personas for this user
        personas = self.get_personas_for_user(user_id)
        
        if not personas:
            # Create default persona
            return self.create_or_update_persona(
                user_id=user_id,
                persona_name=username or "Default",
                metadata={"auto_created": True}
            )
        
        # Simple heuristic: use most recently active persona
        # In production, could use LLM to analyze message style, context, etc.
        if len(personas) == 1:
            return personas[0]["id"]
        
        # Return most recently active persona
        return personas[0]["id"] if personas else None
    
    def track_user_mention(self,
                          user_id: str,
                          mentioned_user_id: str,
                          context: str,
                          channel_id: str,
                          memory_id: str = None,
                          persona_id: Optional[str] = None,
                          mentioned_persona_id: Optional[str] = None):
        """
        Track when one user mentions another user.
        Enhanced to also track persona-level interactions.
        
        Args:
            user_id: User ID who mentioned
            mentioned_user_id: User ID who was mentioned
            context: Context of mention
            channel_id: Channel ID
            memory_id: Memory ID (optional)
            persona_id: Persona ID of user who mentioned (optional)
            mentioned_persona_id: Persona ID of user who was mentioned (optional)
        """
        # Original user-level tracking
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
        
        # Persona-level tracking (if personas provided)
        if persona_id and mentioned_persona_id:
            self.track_persona_interaction(
                persona_id_1=persona_id,
                persona_id_2=mentioned_persona_id,
                interaction_type="mentioned",
                context=context,
                channel_id=channel_id
            )
    
    def close(self):
        """Close connection."""
        self.driver.close()

