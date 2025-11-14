"""
Migration script to sync existing Neo4j documents to Elasticsearch.
This allows you to enable Elasticsearch search for existing documents.
"""
import sys
from src.stores.document_store import DocumentStore
from elasticsearch_store import ElasticsearchStore
from logger_config import logger
from config import ELASTICSEARCH_ENABLED


def migrate_documents():
    """Migrate all documents from Neo4j to Elasticsearch."""
    # Note: We can migrate even if ELASTICSEARCH_ENABLED is false
    # This script will work regardless of the setting
    
    try:
        # Initialize stores
        neo4j_store = DocumentStore()
        es_store = ElasticsearchStore()
        
        # Get all documents from Neo4j
        logger.info("📥 Fetching documents from Neo4j...")
        documents = neo4j_store.get_all_shared_documents()
        
        if not documents:
            logger.info("No documents found in Neo4j")
            return True
        
        logger.info(f"Found {len(documents)} documents to migrate")
        
        # Migrate each document
        success_count = 0
        error_count = 0
        
        for i, doc in enumerate(documents, 1):
            doc_id = doc.get('id')
            file_name = doc.get('file_name', 'Unknown')
            
            logger.info(f"[{i}/{len(documents)}] Migrating: {file_name} ({doc_id})")
            
            try:
                # Get document chunks
                chunks = neo4j_store.get_document_chunks(doc_id)
                
                if not chunks:
                    logger.warning(f"No chunks found for document {doc_id}")
                    continue
                
                # Get embeddings from Neo4j
                # Note: We need to retrieve embeddings from Neo4j chunks
                # This requires querying Neo4j for chunk embeddings
                from neo4j import GraphDatabase
                from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
                
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                with driver.session() as session:
                    result = session.run("""
                        MATCH (d:SharedDocument {id: $doc_id})-[:CONTAINS]->(c:SharedChunk)
                        RETURN c.id AS chunk_id, c.embedding AS embedding, c.text AS text, c.chunk_index AS chunk_index
                        ORDER BY c.chunk_index ASC
                    """, doc_id=doc_id)
                    
                    chunk_data = []
                    embeddings = []
                    for record in result:
                        chunk_data.append({
                            "text": record["text"],
                            "chunk_index": record["chunk_index"]
                        })
                        embeddings.append(record["embedding"])
                
                driver.close()
                
                if not chunk_data:
                    logger.warning(f"No chunk data found for document {doc_id}")
                    continue
                
                # Store document metadata
                es_store.store_document(
                    doc_id=doc_id,
                    file_name=file_name,
                    file_path=doc.get('file_path', ''),
                    file_type=doc.get('file_type', 'unknown'),
                    uploaded_by=doc.get('uploaded_by', 'unknown'),
                    text='',  # We'll store text in chunks
                    chunk_count=len(chunk_data)
                )
                
                # Store chunks with embeddings
                es_store.store_chunks(
                    doc_id=doc_id,
                    file_name=file_name,
                    uploaded_by=doc.get('uploaded_by', 'unknown'),
                    chunks=chunk_data,
                    embeddings=embeddings
                )
                
                success_count += 1
                logger.info(f"✅ Successfully migrated: {file_name}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Failed to migrate {file_name}: {e}")
        
        logger.info(f"\n📊 Migration complete:")
        logger.info(f"   ✅ Success: {success_count}")
        logger.info(f"   ❌ Errors: {error_count}")
        
        # Close connections
        neo4j_store.close()
        es_store.close()
        
        return error_count == 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("🚀 Starting Elasticsearch migration...")
    success = migrate_documents()
    sys.exit(0 if success else 1)

