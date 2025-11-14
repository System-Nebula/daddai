"""
Search for document references in memories and other sources.
"""
from memory_store import MemoryStore
from document_store import DocumentStore
from neo4j_store import Neo4jStore
from logger_config import logger
import re

def search_document_references():
    """Search for document references in all storage systems."""
    logger.info("=" * 60)
    logger.info("Searching for Document References")
    logger.info("=" * 60)
    
    # Documents to search for
    target_docs = [
        "CrowdStrike2025ThreatHuntingReport.pdf",
        "My_Deezer_Library.CSV",
        "kohya-ss-gui_logs5.txt",
        "build-logs-22475bd2"
    ]
    
    # Search in shared documents
    logger.info("\n📁 Searching Shared Documents:")
    logger.info("-" * 60)
    document_store = DocumentStore()
    try:
        shared_docs = document_store.get_all_shared_documents()
        for doc in shared_docs:
            filename = doc.get('file_name', '')
            for target in target_docs:
                if target.lower() in filename.lower():
                    logger.info(f"  ✓ Found: {filename}")
                    logger.info(f"    ID: {doc.get('id')}")
                    logger.info(f"    Uploaded by: {doc.get('uploaded_by')}")
    finally:
        document_store.close()
    
    # Search in personal documents
    logger.info("\n📁 Searching Personal Documents:")
    logger.info("-" * 60)
    neo4j_store = Neo4jStore()
    try:
        personal_docs = neo4j_store.get_all_documents()
        for doc in personal_docs:
            filename = doc.get('file_name', '')
            for target in target_docs:
                if target.lower() in filename.lower():
                    logger.info(f"  ✓ Found: {filename}")
                    logger.info(f"    ID: {doc.get('id')}")
                    logger.info(f"    Path: {doc.get('file_path')}")
    finally:
        neo4j_store.close()
    
    # Search in memories
    logger.info("\n🧠 Searching Memories for Document References:")
    logger.info("-" * 60)
    memory_store = MemoryStore()
    try:
        # Get all channels
        channels = memory_store.get_all_channels()
        
        for channel_id in channels[:10]:  # Check first 10 channels
            try:
                memories = memory_store.get_all_memories(channel_id, limit=100)
                for memory in memories:
                    content = memory.get('content', '')
                    memory_type = memory.get('memory_type', '')
                    
                    # Check if any target document is mentioned
                    for target in target_docs:
                        if target.lower() in content.lower():
                            logger.info(f"  ✓ Found reference in memory:")
                            logger.info(f"    Channel: {channel_id}")
                            logger.info(f"    Type: {memory_type}")
                            logger.info(f"    Content preview: {content[:200]}...")
                            logger.info(f"    Mentions: {target}")
            except Exception as e:
                logger.debug(f"Error checking channel {channel_id}: {e}")
    finally:
        memory_store.close()
    
    # Search in Neo4j directly for any mentions
    logger.info("\n🔍 Searching Neo4j for Document Text References:")
    logger.info("-" * 60)
    from neo4j import GraphDatabase
    from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            # Search in document text fields
            for target in target_docs:
                result = session.run("""
                    MATCH (d)
                    WHERE (d:Document OR d:SharedDocument)
                    AND (toLower(d.file_name) CONTAINS toLower($search) 
                         OR toLower(d.text) CONTAINS toLower($search))
                    RETURN labels(d) as labels, d.file_name as file_name, d.id as id
                    LIMIT 10
                """, search=target)
                
                for record in result:
                    labels = record["labels"]
                    filename = record["file_name"]
                    doc_id = record["id"]
                    logger.info(f"  ✓ Found in {labels[0]}: {filename} (ID: {doc_id})")
    finally:
        driver.close()
    
    logger.info("\n" + "=" * 60)

if __name__ == "__main__":
    search_document_references()

