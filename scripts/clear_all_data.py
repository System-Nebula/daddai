"""
Script to clear ALL data from Neo4j: memories, channels, documents, and chunks.
Note: For comprehensive cleansing including caches, use cleanse_all_data.py
"""
import sys
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger

def clear_all_data():
    """Clear all memories, channels, documents, and chunks from Neo4j."""
    driver = None
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        logger.warning("WARNING: This will delete ALL data from Neo4j!")
        logger.warning("   - All memories")
        logger.warning("   - All channels")
        logger.warning("   - All documents (SharedDocument and Document)")
        logger.warning("   - All chunks (SharedChunk and Chunk)")
        logger.warning("   - All user nodes")
        logger.warning("   - All relationships")
        logger.info("Note: For comprehensive cleansing including caches, use cleanse_all_data.py")
        confirmation = input("Type 'yes' to confirm: ")
        
        if confirmation.lower() != 'yes':
            logger.info("Operation cancelled.")
            return
        
        with driver.session() as session:
            logger.info("Starting data deletion...")
            
            # Delete all relationships first
            result = session.run("MATCH ()-[r]-() DELETE r RETURN count(r) as deleted")
            deleted = result.single()["deleted"]
            logger.info(f"Deleted {deleted} relationships")
            
            # Delete all SharedChunk nodes (shared documents)
            result = session.run("MATCH (c:SharedChunk) DELETE c RETURN count(c) as deleted")
            deleted = result.single()["deleted"]
            logger.info(f"Deleted {deleted} SharedChunk nodes")
            
            # Delete all SharedDocument nodes
            result = session.run("MATCH (d:SharedDocument) DELETE d RETURN count(d) as deleted")
            deleted = result.single()["deleted"]
            logger.info(f"Deleted {deleted} SharedDocument nodes")
            
            # Delete all Chunk nodes (personal documents)
            result = session.run("MATCH (c:Chunk) DELETE c RETURN count(c) as deleted")
            deleted = result.single()["deleted"]
            logger.info(f"Deleted {deleted} Chunk nodes")
            
            # Delete all Document nodes (personal documents)
            result = session.run("MATCH (d:Document) DELETE d RETURN count(d) as deleted")
            deleted = result.single()["deleted"]
            logger.info(f"Deleted {deleted} Document nodes")
            
            # Delete all Memory nodes
            result = session.run("MATCH (m:Memory) DELETE m RETURN count(m) as deleted")
            deleted = result.single()["deleted"]
            logger.info(f"Deleted {deleted} Memory nodes")
            
            # Delete all Channel nodes
            result = session.run("MATCH (c:Channel) DELETE c RETURN count(c) as deleted")
            deleted = result.single()["deleted"]
            logger.info(f"Deleted {deleted} Channel nodes")
            
            # Delete all User nodes
            result = session.run("MATCH (u:User) DELETE u RETURN count(u) as deleted")
            deleted = result.single()["deleted"]
            logger.info(f"Deleted {deleted} User nodes")
            
            logger.info("All data has been cleared from Neo4j!")
            
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        raise
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    clear_all_data()

