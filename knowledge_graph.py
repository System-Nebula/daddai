"""
Knowledge graph system for tracking relationships between:
- Users and documents
- Documents and topics/entities
- Users and topics
- Entities and their relationships
"""
from typing import List, Dict, Any, Optional, Set
from neo4j import GraphDatabase
import json
from datetime import datetime
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger


class KnowledgeGraph:
    """
    Knowledge graph system that tracks relationships between entities.
    Enables:
    - Finding related documents/users/topics
    - Understanding document relationships
    - User-document interactions
    - Topic clustering
    """
    
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        """Initialize knowledge graph."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Initialize knowledge graph schema."""
        with self.driver.session() as session:
            try:
                # Create indexes for faster queries
                session.run("CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name)")
                session.run("CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)")
            except Exception as e:
                logger.debug(f"Schema initialization (may already exist): {e}")
    
    def link_document_to_topic(self,
                               doc_id: str,
                               topic: str,
                               confidence: float = 1.0):
        """Link a document to a topic."""
        with self.driver.session() as session:
            session.run("""
                MATCH (d:SharedDocument {id: $doc_id})
                MERGE (t:Topic {name: $topic})
                MERGE (d)-[r:ABOUT]->(t)
                SET r.confidence = $confidence,
                    r.created_at = datetime()
            """,
                doc_id=doc_id,
                topic=topic.lower(),
                confidence=confidence
            )
    
    def link_user_to_document(self,
                              user_id: str,
                              doc_id: str,
                              relationship_type: str = "VIEWED"):
        """
        Link a user to a document with a relationship.
        Types: VIEWED, UPLOADED, QUERIED, BOOKMARKED
        """
        with self.driver.session() as session:
            session.run("MERGE (u:User {id: $user_id})", user_id=user_id)
            
            session.run(f"""
                MATCH (u:User {{id: $user_id}})
                MATCH (d:SharedDocument {{id: $doc_id}})
                MERGE (u)-[r:{relationship_type}]->(d)
                SET r.count = COALESCE(r.count, 0) + 1,
                    r.last_interaction = datetime()
            """,
                user_id=user_id,
                doc_id=doc_id
            )
    
    def link_entities(self,
                     entity1: str,
                     entity2: str,
                     relationship_type: str,
                     metadata: Dict[str, Any] = None):
        """
        Link two entities with a relationship.
        Examples: (Person)-[KNOWS]->(Person), (Document)-[REFERENCES]->(Document)
        """
        with self.driver.session() as session:
            metadata_json = json.dumps(metadata) if metadata else "{}"
            
            session.run(f"""
                MERGE (e1:Entity {{name: $entity1}})
                MERGE (e2:Entity {{name: $entity2}})
                MERGE (e1)-[r:{relationship_type}]->(e2)
                SET r.metadata = $metadata_json,
                    r.last_updated = datetime(),
                    r.strength = COALESCE(r.strength, 0) + 1
            """,
                entity1=entity1,
                entity2=entity2,
                metadata_json=metadata_json
            )
    
    def extract_and_link_entities(self,
                                  doc_id: str,
                                  text: str,
                                  entities: List[Dict[str, str]]):
        """
        Extract entities from text and link them to document.
        entities: List of {name, type} dicts
        """
        with self.driver.session() as session:
            for entity in entities:
                entity_name = entity.get("name")
                entity_type = entity.get("type", "general")
                
                if not entity_name:
                    continue
                
                session.run("""
                    MATCH (d:SharedDocument {id: $doc_id})
                    MERGE (e:Entity {name: $entity_name})
                    SET e.type = $entity_type
                    MERGE (d)-[:MENTIONS]->(e)
                """,
                    doc_id=doc_id,
                    entity_name=entity_name,
                    entity_type=entity_type
                )
    
    def find_related_documents(self,
                               doc_id: str,
                               max_relations: int = 5) -> List[Dict[str, Any]]:
        """
        Find documents related to a given document.
        Considers:
        - Shared topics
        - Shared entities
        - User interactions
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d1:SharedDocument {id: $doc_id})
                
                // Find documents with shared topics
                OPTIONAL MATCH (d1)-[:ABOUT]->(t:Topic)<-[:ABOUT]-(d2:SharedDocument)
                WHERE d2.id <> $doc_id
                
                // Find documents with shared entities
                OPTIONAL MATCH (d1)-[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(d3:SharedDocument)
                WHERE d3.id <> $doc_id
                
                // Find documents viewed by same users
                OPTIONAL MATCH (d1)<-[:VIEWED]-(u:User)-[:VIEWED]->(d4:SharedDocument)
                WHERE d4.id <> $doc_id
                
                WITH collect(DISTINCT d2) + collect(DISTINCT d3) + collect(DISTINCT d4) AS related_docs
                UNWIND related_docs AS doc
                WHERE doc IS NOT NULL
                
                RETURN DISTINCT doc.id AS doc_id,
                       doc.file_name AS file_name,
                       count(*) AS relation_strength
                ORDER BY relation_strength DESC
                LIMIT $max_relations
            """,
                doc_id=doc_id,
                max_relations=max_relations
            )
            
            related = []
            for record in result:
                related.append({
                    "doc_id": record.get("doc_id"),
                    "file_name": record.get("file_name"),
                    "relation_strength": record.get("relation_strength", 0)
                })
            
            return related
    
    def find_related_users(self,
                          user_id: str,
                          max_relations: int = 10) -> List[Dict[str, Any]]:
        """
        Find users related to a given user.
        Considers:
        - Shared document interests
        - Shared topics
        - Direct interactions
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (u1:User {id: $user_id})
                
                // Find users who viewed same documents
                OPTIONAL MATCH (u1)-[:VIEWED]->(d:SharedDocument)<-[:VIEWED]-(u2:User)
                WHERE u2.id <> $user_id
                
                // Find users with shared interests
                OPTIONAL MATCH (u1)-[:INTERESTED_IN]->(i:Interest)<-[:INTERESTED_IN]-(u3:User)
                WHERE u3.id <> $user_id
                
                // Find direct interactions
                OPTIONAL MATCH (u1)-[:INTERACTS_WITH]->(u4:User)
                
                WITH collect(DISTINCT u2) + collect(DISTINCT u3) + collect(DISTINCT u4) AS related_users
                UNWIND related_users AS user
                WHERE user IS NOT NULL
                
                RETURN DISTINCT user.id AS user_id,
                       user.username AS username,
                       count(*) AS relation_strength
                ORDER BY relation_strength DESC
                LIMIT $max_relations
            """,
                user_id=user_id,
                max_relations=max_relations
            )
            
            related = []
            for record in result:
                related.append({
                    "user_id": record.get("user_id"),
                    "username": record.get("username"),
                    "relation_strength": record.get("relation_strength", 0)
                })
            
            return related
    
    def find_documents_by_topic(self,
                               topic: str,
                               min_confidence: float = 0.5) -> List[Dict[str, Any]]:
        """Find all documents related to a topic."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (t:Topic {name: $topic})<-[:ABOUT]-(d:SharedDocument)
                WHERE r.confidence >= $min_confidence
                RETURN d.id AS doc_id,
                       d.file_name AS file_name,
                       r.confidence AS confidence
                ORDER BY r.confidence DESC
            """,
                topic=topic.lower(),
                min_confidence=min_confidence
            )
            
            documents = []
            for record in result:
                documents.append({
                    "doc_id": record.get("doc_id"),
                    "file_name": record.get("file_name"),
                    "confidence": record.get("confidence", 0)
                })
            
            return documents
    
    def get_topic_clusters(self, min_documents: int = 2) -> List[Dict[str, Any]]:
        """
        Get topic clusters (topics with multiple documents).
        Useful for discovering document themes.
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (t:Topic)<-[:ABOUT]-(d:SharedDocument)
                WITH t, count(d) AS doc_count
                WHERE doc_count >= $min_documents
                RETURN t.name AS topic,
                       doc_count AS document_count
                ORDER BY doc_count DESC
            """,
                min_documents=min_documents
            )
            
            clusters = []
            for record in result:
                clusters.append({
                    "topic": record.get("topic"),
                    "document_count": record.get("document_count", 0)
                })
            
            return clusters
    
    def get_user_document_history(self,
                                  user_id: str,
                                  limit: int = 20) -> List[Dict[str, Any]]:
        """Get user's document interaction history."""
        with self.driver.session() as session:
            # Use OPTIONAL MATCH to avoid warnings when relationships don't exist yet
            result = session.run("""
                MATCH (u:User {id: $user_id})
                OPTIONAL MATCH (u)-[r:VIEWED|UPLOADED|QUERIED]->(d:SharedDocument)
                WHERE r IS NOT NULL AND d IS NOT NULL
                RETURN d.id AS doc_id,
                       d.file_name AS file_name,
                       type(r) AS interaction_type,
                       toString(COALESCE(r.last_interaction, datetime())) AS last_interaction,
                       COALESCE(r.count, 0) AS interaction_count
                ORDER BY r.last_interaction DESC NULLS LAST
                LIMIT $limit
            """,
                user_id=user_id,
                limit=limit
            )
            
            history = []
            for record in result:
                history.append({
                    "doc_id": record.get("doc_id"),
                    "file_name": record.get("file_name"),
                    "interaction_type": record.get("interaction_type"),
                    "last_interaction": record.get("last_interaction"),
                    "interaction_count": record.get("interaction_count", 0)
                })
            
            return history
    
    def close(self):
        """Close connection."""
        self.driver.close()

