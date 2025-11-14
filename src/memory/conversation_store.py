"""
Conversation storage in Neo4j for Discord bot.
Stores user conversations with question/answer pairs, timestamps, and relationships.
Supports semantic retrieval for relevant conversation context.
"""
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import json
from datetime import datetime
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBEDDING_DIMENSION
from logger_config import logger


def sanitize_unicode(text: str) -> str:
    """
    Sanitize Unicode text by removing invalid surrogate characters.
    These can't be encoded in UTF-8 and cause errors when saving to Neo4j.
    
    Args:
        text: Input text that may contain invalid Unicode
        
    Returns:
        Sanitized text safe for UTF-8 encoding
    """
    if not text:
        return text
    
    # Remove invalid surrogate characters (U+D800 to U+DFFF)
    # These are invalid in UTF-8 and cause encoding errors
    result = []
    for char in text:
        code = ord(char)
        # Check if it's a surrogate (invalid UTF-8)
        # Surrogates are in range U+D800 to U+DFFF
        if 0xD800 <= code <= 0xDFFF:
            # Replace with replacement character or skip
            result.append('\ufffd')  # Unicode replacement character
        else:
            try:
                # Verify the character can be encoded in UTF-8
                char.encode('utf-8')
                result.append(char)
            except UnicodeEncodeError:
                # If encoding fails, replace with replacement character
                result.append('\ufffd')
    
    sanitized = ''.join(result)
    
    # Final check: ensure the entire string can be encoded
    try:
        sanitized.encode('utf-8')
        return sanitized
    except UnicodeEncodeError:
        # Last resort: encode with errors='replace' to remove any remaining issues
        return sanitized.encode('utf-8', errors='replace').decode('utf-8', errors='replace')


class ConversationStore:
    """
    Store and retrieve user conversations in Neo4j.
    Each conversation entry links a User to a ConversationMessage node.
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD, embedding_generator=None):
        """Initialize conversation store."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.embedding_generator = embedding_generator  # For semantic search
        self.embedding_dimension = EMBEDDING_DIMENSION
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize conversation schema in Neo4j."""
        with self.driver.session() as session:
            try:
                # Create constraints
                session.run("CREATE CONSTRAINT conversation_message_id IF NOT EXISTS FOR (c:ConversationMessage) REQUIRE c.id IS UNIQUE")
                session.run("CREATE INDEX conversation_user IF NOT EXISTS FOR (c:ConversationMessage) ON (c.user_id)")
                session.run("CREATE INDEX conversation_timestamp IF NOT EXISTS FOR (c:ConversationMessage) ON (c.timestamp)")
                
                # Try to create vector index for semantic search
                try:
                    session.run(f"""
                        CREATE VECTOR INDEX conversation_embeddings IF NOT EXISTS
                        FOR (c:ConversationMessage) ON c.embedding
                        OPTIONS {{
                            indexConfig: {{
                                `vector.dimensions`: {self.embedding_dimension},
                                `vector.similarity_function`: 'cosine'
                            }}
                        }}
                    """)
                    self.use_vector_index = True
                except Exception as e:
                    logger.debug(f"Vector index creation (may not be supported): {e}")
                    self.use_vector_index = False
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def add_message(self, user_id: str, question: str, answer: str, channel_id: Optional[str] = None, embedding: Optional[List[float]] = None) -> str:
        """
        Add a conversation message (question/answer pair) for a user.
        Stores embedding for semantic search if available.
        
        Args:
            user_id: Discord user ID
            question: User's question
            answer: Bot's answer
            channel_id: Optional Discord channel ID
            embedding: Optional embedding vector for semantic search
            
        Returns:
            Message ID
        """
        message_id = f"conv_{user_id}_{datetime.now().timestamp()}"
        timestamp = datetime.now().isoformat()
        
        # Sanitize Unicode to remove invalid surrogates before saving
        question = sanitize_unicode(question)
        answer = sanitize_unicode(answer)
        
        # Generate embedding if not provided but generator is available
        if embedding is None and self.embedding_generator:
            try:
                # Use question + answer for better semantic matching
                combined_text = f"{question} {answer}"[:1000]  # Limit for embedding
                embedding = self.embedding_generator.generate_embedding(combined_text)
            except Exception as e:
                logger.debug(f"Could not generate embedding for conversation: {e}")
                embedding = None
        
        with self.driver.session() as session:
            # Ensure User node exists
            session.run("MERGE (u:User {id: $user_id})", user_id=user_id)
            
            # Create conversation message node with optional embedding
            if embedding:
                session.run("""
                    MATCH (u:User {id: $user_id})
                    CREATE (m:ConversationMessage {
                        id: $message_id,
                        user_id: $user_id,
                        question: $question,
                        answer: $answer,
                        timestamp: $timestamp,
                        channel_id: COALESCE($channel_id, null),
                        embedding: $embedding
                    })
                    CREATE (u)-[:HAS_CONVERSATION]->(m)
                """,
                    user_id=user_id,
                    message_id=message_id,
                    question=question[:2000],  # Limit question length
                    answer=answer[:5000],  # Limit answer length
                    timestamp=timestamp,
                    channel_id=channel_id,
                    embedding=embedding
                )
            else:
                session.run("""
                    MATCH (u:User {id: $user_id})
                    CREATE (m:ConversationMessage {
                        id: $message_id,
                        user_id: $user_id,
                        question: $question,
                        answer: $answer,
                        timestamp: $timestamp,
                        channel_id: COALESCE($channel_id, null)
                    })
                    CREATE (u)-[:HAS_CONVERSATION]->(m)
                """,
                    user_id=user_id,
                    message_id=message_id,
                    question=question[:2000],
                    answer=answer[:5000],
                    timestamp=timestamp,
                    channel_id=channel_id
                )
            
            # No automatic cleanup - keep all conversations for long-term memory
        
        return message_id
    
    def get_conversation(self, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get conversation history for a user.
        
        Args:
            user_id: Discord user ID
            limit: Maximum number of messages to retrieve (None = all messages)
            
        Returns:
            List of conversation messages in chronological order
        """
        with self.driver.session() as session:
            # Build query with optional limit
            if limit:
                query = """
                    MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(m:ConversationMessage)
                    RETURN m.question AS question,
                           m.answer AS answer,
                           m.timestamp AS timestamp,
                           m.channel_id AS channel_id
                    ORDER BY m.timestamp ASC
                    LIMIT $limit
                """
                result = session.run(query, user_id=user_id, limit=limit)
            else:
                # Get all messages (no limit)
                query = """
                    MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(m:ConversationMessage)
                    RETURN m.question AS question,
                           m.answer AS answer,
                           m.timestamp AS timestamp,
                           m.channel_id AS channel_id
                    ORDER BY m.timestamp ASC
                """
                result = session.run(query, user_id=user_id)
            
            messages = []
            for record in result:
                messages.append({
                    "question": record.get("question"),
                    "answer": record.get("answer"),
                    "timestamp": record.get("timestamp"),
                    "channel_id": record.get("channel_id")
                })
            
            return messages
    
    def get_recent_conversation(self, user_id: str, max_messages: int = 5, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get recent conversation messages for a user.
        Can optionally filter by time period for better performance with large histories.
        
        Args:
            user_id: Discord user ID
            max_messages: Maximum number of recent messages to retrieve
            days: Optional: Only get messages from last N days (None = all time)
            
        Returns:
            List of recent conversation messages (most recent first, then reversed to chronological)
        """
        with self.driver.session() as session:
            if days:
                # Filter by time period for better performance
                result = session.run("""
                    MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(m:ConversationMessage)
                    WHERE m.timestamp >= datetime() - duration({days: $days})
                    RETURN m.question AS question,
                           m.answer AS answer,
                           m.timestamp AS timestamp,
                           m.channel_id AS channel_id
                    ORDER BY m.timestamp DESC
                    LIMIT $max_messages
                """,
                    user_id=user_id,
                    max_messages=max_messages,
                    days=days
                )
            else:
                # Get most recent messages (no time filter)
                result = session.run("""
                    MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(m:ConversationMessage)
                    RETURN m.question AS question,
                           m.answer AS answer,
                           m.timestamp AS timestamp,
                           m.channel_id AS channel_id
                    ORDER BY m.timestamp DESC
                    LIMIT $max_messages
                """,
                    user_id=user_id,
                    max_messages=max_messages
                )
            
            messages = []
            for record in result:
                messages.append({
                    "question": record.get("question"),
                    "answer": record.get("answer"),
                    "timestamp": record.get("timestamp"),
                    "channel_id": record.get("channel_id")
                })
            
            # Reverse to get chronological order (oldest first)
            return list(reversed(messages))
    
    def get_relevant_conversations(self, user_id: str, query: str, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Get semantically relevant conversations for a user based on query.
        Uses vector similarity search to find conversations related to the current query.
        
        Args:
            user_id: Discord user ID
            query: Current query text (for fallback)
            query_embedding: Embedding vector of the query
            top_k: Number of relevant conversations to retrieve
            
        Returns:
            List of relevant conversation messages (most relevant first)
        """
        if not query_embedding or not self.use_vector_index:
            # Fallback to recent conversations if no embedding/vector index
            return self.get_recent_conversation(user_id, max_messages=top_k)
        
        with self.driver.session() as session:
            try:
                # Use vector similarity search if available
                if self.use_vector_index:
                    result = session.run("""
                        MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(m:ConversationMessage)
                        WHERE m.embedding IS NOT NULL
                        WITH m, vector.similarity.cosine(m.embedding, $query_embedding) AS similarity
                        WHERE similarity > 0.3
                        RETURN m.question AS question,
                               m.answer AS answer,
                               m.timestamp AS timestamp,
                               m.channel_id AS channel_id,
                               similarity
                        ORDER BY similarity DESC
                        LIMIT $top_k
                    """,
                        user_id=user_id,
                        query_embedding=query_embedding,
                        top_k=top_k
                    )
                else:
                    # Fallback: keyword-based search
                    query_lower = query.lower()
                    keywords = [w for w in query_lower.split() if len(w) > 3][:5]
                    result = session.run("""
                        MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(m:ConversationMessage)
                        WHERE ANY(keyword IN $keywords WHERE 
                            toLower(m.question) CONTAINS keyword OR 
                            toLower(m.answer) CONTAINS keyword)
                        RETURN m.question AS question,
                               m.answer AS answer,
                               m.timestamp AS timestamp,
                               m.channel_id AS channel_id,
                               0.5 AS similarity
                        ORDER BY m.timestamp DESC
                        LIMIT $top_k
                    """,
                        user_id=user_id,
                        keywords=keywords,
                        top_k=top_k
                    )
                
                messages = []
                for record in result:
                    messages.append({
                        "question": record.get("question"),
                        "answer": record.get("answer"),
                        "timestamp": record.get("timestamp"),
                        "channel_id": record.get("channel_id"),
                        "relevance_score": record.get("similarity", 0.5)
                    })
                
                return messages
            except Exception as e:
                logger.warning(f"Error in semantic conversation retrieval: {e}")
                # Fallback to recent conversations
                return self.get_recent_conversation(user_id, max_messages=top_k)
    
    def clear_conversation(self, user_id: str) -> bool:
        """
        Clear all conversation history for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            True if successful
        """
        with self.driver.session() as session:
            try:
                session.run("""
                    MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(m:ConversationMessage)
                    DETACH DELETE m
                """,
                    user_id=user_id
                )
                return True
            except Exception as e:
                logger.error(f"Error clearing conversation for {user_id}: {e}")
                return False
    
    def get_conversation_count(self, user_id: str) -> int:
        """
        Get the number of conversation messages for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Number of messages
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(m:ConversationMessage)
                RETURN count(m) AS count
            """,
                user_id=user_id
            )
            
            record = result.single()
            return record.get("count", 0) if record else 0
    
    def get_conversation_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get conversation statistics for a user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Dictionary with stats: total_messages, oldest_message, newest_message
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u:User {id: $user_id})-[:HAS_CONVERSATION]->(m:ConversationMessage)
                WITH m
                ORDER BY m.timestamp ASC
                WITH collect(m) AS messages
                RETURN 
                    size(messages) AS total_messages,
                    messages[0].timestamp AS oldest_message,
                    messages[-1].timestamp AS newest_message
            """,
                user_id=user_id
            )
            
            record = result.single()
            if record:
                return {
                    "total_messages": record.get("total_messages", 0),
                    "oldest_message": record.get("oldest_message"),
                    "newest_message": record.get("newest_message")
                }
            return {
                "total_messages": 0,
                "oldest_message": None,
                "newest_message": None
            }
    
    def close(self):
        """Close Neo4j connection."""
        self.driver.close()

