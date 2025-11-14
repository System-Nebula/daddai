"""
Conversation threading and topic tracking system.
Tracks conversation threads, topics, and context across multiple interactions.
"""
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import json
from datetime import datetime, timedelta
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger


class ConversationThreading:
    """
    Conversation threading system that:
    - Tracks conversation threads by topic/channel
    - Links related conversations
    - Maintains conversation context
    - Identifies conversation topics
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize conversation threading."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize conversation threading schema."""
        with self.driver.session() as session:
            try:
                session.run("CREATE CONSTRAINT thread_id IF NOT EXISTS FOR (t:Thread) REQUIRE t.id IS UNIQUE")
                session.run("CREATE INDEX thread_channel IF NOT EXISTS FOR (t:Thread) ON (t.channel_id)")
                session.run("CREATE INDEX thread_topic IF NOT EXISTS FOR (t:Thread) ON (t.topic)")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def create_or_get_thread(self,
                             channel_id: str,
                             topic: str,
                             initial_message: str = None) -> str:
        """
        Create a new conversation thread or get existing active thread.
        
        Args:
            channel_id: Channel ID
            topic: Thread topic
            initial_message: Initial message in thread
            
        Returns:
            Thread ID
        """
        with self.driver.session() as session:
            # Check for existing active thread with same topic
            result = session.run("""
                MATCH (t:Thread {channel_id: $channel_id, topic: $topic, active: true})
                WHERE t.last_activity > datetime() - duration({hours: 2})
                RETURN t.id AS thread_id
                ORDER BY t.last_activity DESC
                LIMIT 1
            """,
                channel_id=channel_id,
                topic=topic.lower()
            )
            
            record = result.single()
            if record:
                thread_id = record.get("thread_id")
                # Update last activity
                session.run("""
                    MATCH (t:Thread {id: $thread_id})
                    SET t.last_activity = datetime(),
                        t.message_count = COALESCE(t.message_count, 0) + 1
                """,
                    thread_id=thread_id
                )
                return thread_id
            
            # Create new thread
            thread_id = f"thread_{channel_id}_{datetime.now().timestamp()}"
            
            session.run("""
                CREATE (t:Thread {
                    id: $thread_id,
                    channel_id: $channel_id,
                    topic: $topic,
                    active: true,
                    created_at: datetime(),
                    last_activity: datetime(),
                    message_count: 1,
                    initial_message: $initial_message
                })
            """,
                thread_id=thread_id,
                channel_id=channel_id,
                topic=topic.lower(),
                initial_message=initial_message[:500] if initial_message else None
            )
            
            return thread_id
    
    def add_message_to_thread(self,
                            thread_id: str,
                            message: str,
                            user_id: str = None,
                            message_type: str = "user"):
        """
        Add a message to a conversation thread.
        
        Args:
            thread_id: Thread ID
            message: Message content
            user_id: User who sent the message
            message_type: Type (user, bot, system)
        """
        with self.driver.session() as session:
            message_id = f"msg_{thread_id}_{datetime.now().timestamp()}"
            
            session.run("""
                MATCH (t:Thread {id: $thread_id})
                CREATE (m:Message {
                    id: $message_id,
                    content: $message,
                    message_type: $message_type,
                    user_id: $user_id,
                    created_at: datetime()
                })
                CREATE (t)-[:CONTAINS]->(m)
                SET t.last_activity = datetime(),
                    t.message_count = COALESCE(t.message_count, 0) + 1
            """,
                thread_id=thread_id,
                message_id=message_id,
                message=message[:2000],
                message_type=message_type,
                user_id=user_id
            )
    
    def get_thread_context(self,
                          thread_id: str,
                          max_messages: int = 10) -> Dict[str, Any]:
        """
        Get conversation context for a thread.
        
        Returns:
            Thread context with recent messages
        """
        with self.driver.session() as session:
            # Get thread info
            thread_result = session.run("""
                MATCH (t:Thread {id: $thread_id})
                RETURN t.topic AS topic,
                       t.channel_id AS channel_id,
                       t.message_count AS message_count,
                       toString(t.created_at) AS created_at,
                       toString(t.last_activity) AS last_activity
            """,
                thread_id=thread_id
            )
            
            thread_info = thread_result.single()
            if not thread_info:
                return {}
            
            # Get recent messages
            messages_result = session.run("""
                MATCH (t:Thread {id: $thread_id})-[:CONTAINS]->(m:Message)
                RETURN m.content AS content,
                       m.message_type AS message_type,
                       m.user_id AS user_id,
                       toString(m.created_at) AS created_at
                ORDER BY m.created_at DESC
                LIMIT $max_messages
            """,
                thread_id=thread_id,
                max_messages=max_messages
            )
            
            messages = []
            for record in messages_result:
                messages.append({
                    "content": record.get("content"),
                    "message_type": record.get("message_type"),
                    "user_id": record.get("user_id"),
                    "created_at": record.get("created_at")
                })
            
            # Reverse to chronological order
            messages.reverse()
            
            return {
                "thread_id": thread_id,
                "topic": thread_info.get("topic"),
                "channel_id": thread_info.get("channel_id"),
                "message_count": thread_info.get("message_count", 0),
                "created_at": thread_info.get("created_at"),
                "last_activity": thread_info.get("last_activity"),
                "messages": messages
            }
    
    def find_related_threads(self,
                             thread_id: str,
                             max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Find threads related to the current thread.
        Considers:
        - Same topic
        - Same channel
        - Similar users
        """
        with self.driver.session() as session:
            # Get current thread info
            current_thread = session.run("""
                MATCH (t:Thread {id: $thread_id})
                RETURN t.topic AS topic, t.channel_id AS channel_id
            """,
                thread_id=thread_id
            ).single()
            
            if not current_thread:
                return []
            
            topic = current_thread.get("topic")
            channel_id = current_thread.get("channel_id")
            
            # Find related threads
            result = session.run("""
                MATCH (t:Thread)
                WHERE t.id <> $thread_id
                    AND (t.topic = $topic OR t.channel_id = $channel_id)
                    AND t.active = true
                RETURN t.id AS thread_id,
                       t.topic AS topic,
                       t.channel_id AS channel_id,
                       t.message_count AS message_count,
                       toString(t.last_activity) AS last_activity
                ORDER BY t.last_activity DESC
                LIMIT $max_results
            """,
                thread_id=thread_id,
                topic=topic,
                channel_id=channel_id,
                max_results=max_results
            )
            
            related = []
            for record in result:
                related.append({
                    "thread_id": record.get("thread_id"),
                    "topic": record.get("topic"),
                    "channel_id": record.get("channel_id"),
                    "message_count": record.get("message_count", 0),
                    "last_activity": record.get("last_activity")
                })
            
            return related
    
    def link_threads(self,
                    thread_id1: str,
                    thread_id2: str,
                    relationship_type: str = "RELATED"):
        """Link two threads as related."""
        with self.driver.session() as session:
            session.run(f"""
                MATCH (t1:Thread {{id: $thread_id1}})
                MATCH (t2:Thread {{id: $thread_id2}})
                MERGE (t1)-[r:{relationship_type}]->(t2)
                SET r.created_at = datetime()
            """,
                thread_id1=thread_id1,
                thread_id2=thread_id2
            )
    
    def close_inactive_threads(self,
                              max_inactivity_hours: int = 24):
        """Close threads that haven't been active recently."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (t:Thread)
                WHERE t.active = true
                    AND t.last_activity < datetime() - duration({hours: $max_inactivity_hours})
                SET t.active = false,
                    t.closed_at = datetime()
                RETURN count(t) AS closed_count
            """,
                max_inactivity_hours=max_inactivity_hours
            )
            
            record = result.single()
            return record.get("closed_count", 0) if record else 0
    
    def get_active_threads(self,
                          channel_id: str,
                          limit: int = 10) -> List[Dict[str, Any]]:
        """Get active threads for a channel."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (t:Thread {channel_id: $channel_id, active: true})
                RETURN t.id AS thread_id,
                       t.topic AS topic,
                       t.message_count AS message_count,
                       toString(t.last_activity) AS last_activity
                ORDER BY t.last_activity DESC
                LIMIT $limit
            """,
                channel_id=channel_id,
                limit=limit
            )
            
            threads = []
            for record in result:
                threads.append({
                    "thread_id": record.get("thread_id"),
                    "topic": record.get("topic"),
                    "message_count": record.get("message_count", 0),
                    "last_activity": record.get("last_activity")
                })
            
            return threads
    
    def extract_topic(self, message: str) -> str:
        """
        Extract topic from message.
        Simple keyword-based extraction (can be enhanced with LLM).
        """
        message_lower = message.lower()
        
        # Common question starters
        question_words = ["what", "who", "when", "where", "why", "how", "which"]
        
        # Find first significant word after question word
        words = message_lower.split()
        for i, word in enumerate(words):
            if word in question_words and i + 1 < len(words):
                # Get next few words as topic
                topic_words = words[i+1:i+4]
                return " ".join(topic_words)
        
        # If no question word, use first few words
        if words:
            return " ".join(words[:3])
        
        return "general"
    
    def close(self):
        """Close connection."""
        self.driver.close()

