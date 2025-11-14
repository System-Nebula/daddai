"""
List all documents stored in both personal and shared document stores.
"""
import sys
from src.stores.neo4j_store import Neo4jStore
from src.stores.document_store import DocumentStore
from logger_config import logger

def list_all_documents():
    """List all documents from both storage systems."""
    logger.info("=" * 60)
    logger.info("Listing All Documents")
    logger.info("=" * 60)
    
    # Personal documents (Document/Chunk nodes)
    logger.info("\n📁 PERSONAL DOCUMENTS (Document/Chunk nodes):")
    logger.info("-" * 60)
    try:
        neo4j_store = Neo4jStore()
        personal_docs = neo4j_store.get_all_documents()
        
        if personal_docs:
            for i, doc in enumerate(personal_docs, 1):
                logger.info(f"{i}. {doc.get('file_name', 'Unknown')}")
                logger.info(f"   ID: {doc.get('id', 'N/A')}")
                logger.info(f"   Path: {doc.get('file_path', 'N/A')}")
                logger.info(f"   Type: {doc.get('file_type', 'N/A')}")
        else:
            logger.info("   No personal documents found.")
    except Exception as e:
        logger.error(f"Error listing personal documents: {e}", exc_info=True)
    finally:
        neo4j_store.close()
    
    # Shared documents (SharedDocument/SharedChunk nodes)
    logger.info("\n📁 SHARED DOCUMENTS (SharedDocument/SharedChunk nodes):")
    logger.info("-" * 60)
    try:
        document_store = DocumentStore()
        shared_docs = document_store.get_all_shared_documents()
        
        if shared_docs:
            for i, doc in enumerate(shared_docs, 1):
                logger.info(f"{i}. {doc.get('file_name', 'Unknown')}")
                logger.info(f"   ID: {doc.get('id', 'N/A')}")
                logger.info(f"   Uploaded by: {doc.get('uploaded_by', 'N/A')}")
                logger.info(f"   Uploaded at: {doc.get('uploaded_at', 'N/A')}")
                logger.info(f"   Chunks: {doc.get('chunk_count', 0)}")
        else:
            logger.info("   No shared documents found.")
    except Exception as e:
        logger.error(f"Error listing shared documents: {e}", exc_info=True)
    finally:
        document_store.close()
    
    logger.info("\n" + "=" * 60)
    logger.info("Summary:")
    logger.info(f"  Personal documents: {len(personal_docs) if 'personal_docs' in locals() else 0}")
    logger.info(f"  Shared documents: {len(shared_docs) if 'shared_docs' in locals() else 0}")
    logger.info("=" * 60)

if __name__ == "__main__":
    list_all_documents()

