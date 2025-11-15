"""
Script to clear all documents and memories from both Neo4j and Elasticsearch.
Use with caution - this will delete ALL data!
"""
import sys
import os
import argparse

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from logger_config import logger

def clear_neo4j_documents():
    """Clear all documents from Neo4j."""
    try:
        from src.stores.document_store import DocumentStore
        from neo4j import GraphDatabase
        from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        
        logger.info("Clearing Neo4j documents...")
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session() as session:
            # Delete all shared chunks
            result = session.run("""
                MATCH (c:SharedChunk)
                RETURN count(c) as count
            """)
            chunk_count = result.single()["count"]
            
            session.run("""
                MATCH (c:SharedChunk)
                DETACH DELETE c
            """)
            logger.info(f"  Deleted {chunk_count} shared chunks")
            
            # Delete all shared documents
            result = session.run("""
                MATCH (d:SharedDocument)
                RETURN count(d) as count
            """)
            doc_count = result.single()["count"]
            
            session.run("""
                MATCH (d:SharedDocument)
                DETACH DELETE d
            """)
            logger.info(f"  Deleted {doc_count} shared documents")
            
            # Delete personal documents
            result = session.run("""
                MATCH (d:Document)
                RETURN count(d) as count
            """)
            personal_doc_count = result.single()["count"]
            
            session.run("""
                MATCH (d:Document)
                DETACH DELETE d
            """)
            logger.info(f"  Deleted {personal_doc_count} personal documents")
        
        driver.close()
        return chunk_count + doc_count + personal_doc_count
    except Exception as e:
        logger.error(f"Error clearing Neo4j documents: {e}")
        return 0

def clear_neo4j_memories():
    """Clear all memories from Neo4j."""
    try:
        from neo4j import GraphDatabase
        from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        
        logger.info("Clearing Neo4j memories...")
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session() as session:
            # Delete all memories
            result = session.run("""
                MATCH (m:Memory)
                RETURN count(m) as count
            """)
            memory_count = result.single()["count"]
            
            session.run("""
                MATCH (m:Memory)
                DETACH DELETE m
            """)
            logger.info(f"  Deleted {memory_count} memories")
            
            # Optionally delete empty channels
            session.run("""
                MATCH (c:Channel)
                WHERE NOT (c)-[:HAS_MEMORY]->()
                DELETE c
            """)
        
        driver.close()
        return memory_count
    except Exception as e:
        logger.error(f"Error clearing Neo4j memories: {e}")
        return 0

def clear_elasticsearch_documents():
    """Clear all documents from Elasticsearch."""
    try:
        from config import ELASTICSEARCH_ENABLED
        if not ELASTICSEARCH_ENABLED:
            logger.info("Elasticsearch not enabled, skipping...")
            return 0
        
        from src.stores.elasticsearch_store import ElasticsearchStore
        
        logger.info("Clearing Elasticsearch documents...")
        es_store = ElasticsearchStore()
        
        # Delete all documents from indices
        try:
            # Delete all chunks
            result = es_store.client.delete_by_query(
                index=es_store.chunk_index_name,
                body={"query": {"match_all": {}}}
            )
            chunk_count = result.get("deleted", 0)
            logger.info(f"  Deleted {chunk_count} chunks from Elasticsearch")
        except Exception as e:
            logger.warning(f"  Error deleting chunks: {e}")
            chunk_count = 0
        
        try:
            # Delete all documents
            result = es_store.client.delete_by_query(
                index=es_store.index_name,
                body={"query": {"match_all": {}}}
            )
            doc_count = result.get("deleted", 0)
            logger.info(f"  Deleted {doc_count} documents from Elasticsearch")
        except Exception as e:
            logger.warning(f"  Error deleting documents: {e}")
            doc_count = 0
        
        es_store.close()
        return chunk_count + doc_count
    except Exception as e:
        logger.error(f"Error clearing Elasticsearch documents: {e}")
        return 0

def clear_elasticsearch_memories():
    """Clear all memories from Elasticsearch."""
    try:
        from config import ELASTICSEARCH_ENABLED
        if not ELASTICSEARCH_ENABLED:
            logger.info("Elasticsearch not enabled, skipping...")
            return 0
        
        from elasticsearch import Elasticsearch
        from config import (
            ELASTICSEARCH_HOST, ELASTICSEARCH_PORT, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD,
            ELASTICSEARCH_USE_SSL, ELASTICSEARCH_VERIFY_CERTS
        )
        
        logger.info("Clearing Elasticsearch memories...")
        
        # Build connection URL
        scheme = "https" if ELASTICSEARCH_USE_SSL else "http"
        url = f"{scheme}://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"
        
        connection_params = {"request_timeout": 30}
        if ELASTICSEARCH_USE_SSL:
            connection_params["verify_certs"] = ELASTICSEARCH_VERIFY_CERTS
        else:
            connection_params["verify_certs"] = False
        
        if ELASTICSEARCH_USER and ELASTICSEARCH_PASSWORD:
            connection_params["basic_auth"] = (ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD)
        
        es_client = Elasticsearch(url, **connection_params)
        
        memory_count = 0
        try:
            # Delete all memory chunks
            if es_client.indices.exists(index="memory_chunks"):
                result = es_client.delete_by_query(
                    index="memory_chunks",
                    body={"query": {"match_all": {}}}
                )
                memory_count = result.get("deleted", 0)
                logger.info(f"  Deleted {memory_count} memories from Elasticsearch")
        except Exception as e:
            logger.warning(f"  Error deleting memories: {e}")
        
        es_client.close()
        return memory_count
    except Exception as e:
        logger.error(f"Error clearing Elasticsearch memories: {e}")
        return 0

def get_counts():
    """Get counts of documents and memories before deletion."""
    counts = {
        "neo4j_documents": 0,
        "neo4j_memories": 0,
        "elasticsearch_documents": 0,
        "elasticsearch_memories": 0
    }
    
    try:
        from neo4j import GraphDatabase
        from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            # Count documents
            result = session.run("MATCH (d:SharedDocument) RETURN count(d) as count")
            counts["neo4j_documents"] += result.single()["count"]
            
            result = session.run("MATCH (d:Document) RETURN count(d) as count")
            counts["neo4j_documents"] += result.single()["count"]
            
            # Count memories
            result = session.run("MATCH (m:Memory) RETURN count(m) as count")
            counts["neo4j_memories"] = result.single()["count"]
        
        driver.close()
    except Exception as e:
        logger.warning(f"Error getting Neo4j counts: {e}")
    
    try:
        from config import ELASTICSEARCH_ENABLED
        if ELASTICSEARCH_ENABLED:
            from src.stores.elasticsearch_store import ElasticsearchStore
            
            es_store = ElasticsearchStore()
            
            # Count Elasticsearch documents
            try:
                result = es_store.client.count(index=es_store.chunk_index_name)
                counts["elasticsearch_documents"] += result.get("count", 0)
            except:
                pass
            
            try:
                result = es_store.client.count(index=es_store.index_name)
                counts["elasticsearch_documents"] += result.get("count", 0)
            except:
                pass
            
            # Count Elasticsearch memories
            try:
                from elasticsearch import Elasticsearch
                from config import (
                    ELASTICSEARCH_HOST, ELASTICSEARCH_PORT, ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD,
                    ELASTICSEARCH_USE_SSL, ELASTICSEARCH_VERIFY_CERTS
                )
                
                scheme = "https" if ELASTICSEARCH_USE_SSL else "http"
                url = f"{scheme}://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"
                
                connection_params = {"request_timeout": 30}
                if ELASTICSEARCH_USE_SSL:
                    connection_params["verify_certs"] = ELASTICSEARCH_VERIFY_CERTS
                else:
                    connection_params["verify_certs"] = False
                
                if ELASTICSEARCH_USER and ELASTICSEARCH_PASSWORD:
                    connection_params["basic_auth"] = (ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD)
                
                es_client = Elasticsearch(url, **connection_params)
                
                if es_client.indices.exists(index="memory_chunks"):
                    result = es_client.count(index="memory_chunks")
                    counts["elasticsearch_memories"] = result.get("count", 0)
                
                es_client.close()
            except:
                pass
            
            es_store.close()
    except Exception as e:
        logger.warning(f"Error getting Elasticsearch counts: {e}")
    
    return counts

def main():
    parser = argparse.ArgumentParser(description='Clear all documents and memories from Neo4j and Elasticsearch')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--documents-only', action='store_true', help='Only clear documents, keep memories')
    parser.add_argument('--memories-only', action='store_true', help='Only clear memories, keep documents')
    parser.add_argument('--neo4j-only', action='store_true', help='Only clear Neo4j data')
    parser.add_argument('--elasticsearch-only', action='store_true', help='Only clear Elasticsearch data')
    
    args = parser.parse_args()
    
    # Get counts before deletion
    logger.info("=" * 60)
    logger.info("Data Deletion Summary")
    logger.info("=" * 60)
    
    counts = get_counts()
    
    logger.info("\nCurrent data counts:")
    logger.info(f"  Neo4j Documents: {counts['neo4j_documents']}")
    logger.info(f"  Neo4j Memories: {counts['neo4j_memories']}")
    logger.info(f"  Elasticsearch Documents: {counts['elasticsearch_documents']}")
    logger.info(f"  Elasticsearch Memories: {counts['elasticsearch_memories']}")
    
    total = sum(counts.values())
    if total == 0:
        logger.info("\n✅ No data to delete!")
        return
    
    # Determine what to delete
    delete_documents = not args.memories_only
    delete_memories = not args.documents_only
    delete_neo4j = not args.elasticsearch_only
    delete_elasticsearch = not args.neo4j_only
    
    logger.info("\nWill delete:")
    if delete_documents and delete_neo4j:
        logger.info(f"  ✓ Neo4j Documents ({counts['neo4j_documents']})")
    if delete_memories and delete_neo4j:
        logger.info(f"  ✓ Neo4j Memories ({counts['neo4j_memories']})")
    if delete_documents and delete_elasticsearch:
        logger.info(f"  ✓ Elasticsearch Documents ({counts['elasticsearch_documents']})")
    if delete_memories and delete_elasticsearch:
        logger.info(f"  ✓ Elasticsearch Memories ({counts['elasticsearch_memories']})")
    
    # Confirmation
    if not args.confirm:
        logger.info("\n⚠️  WARNING: This will permanently delete all selected data!")
        response = input("Type 'DELETE' to confirm: ")
        if response != "DELETE":
            logger.info("Cancelled.")
            return
    
    logger.info("\n" + "=" * 60)
    logger.info("Deleting Data...")
    logger.info("=" * 60)
    
    total_deleted = 0
    
    # Delete documents
    if delete_documents:
        if delete_neo4j:
            deleted = clear_neo4j_documents()
            total_deleted += deleted
        
        if delete_elasticsearch:
            deleted = clear_elasticsearch_documents()
            total_deleted += deleted
    
    # Delete memories
    if delete_memories:
        if delete_neo4j:
            deleted = clear_neo4j_memories()
            total_deleted += deleted
        
        if delete_elasticsearch:
            deleted = clear_elasticsearch_memories()
            total_deleted += deleted
    
    logger.info("\n" + "=" * 60)
    logger.info(f"✅ Deletion complete! Deleted {total_deleted} items total.")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()

