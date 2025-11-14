"""
Delete a specific shared document by filename or ID.
"""
import sys
import argparse
from src.stores.document_store import DocumentStore
from logger_config import logger

def delete_shared_document(filename=None, doc_id=None):
    """
    Delete a shared document by filename or ID.
    
    Args:
        filename: Filename to delete (partial match supported)
        doc_id: Document ID to delete
    """
    if not filename and not doc_id:
        logger.error("Error: Must provide either --filename or --doc-id")
        return False
    
    document_store = DocumentStore()
    
    try:
        # Get all documents to find matches
        all_docs = document_store.get_all_shared_documents()
        
        if doc_id:
            # Delete by exact ID
            matching_docs = [doc for doc in all_docs if doc.get('id') == doc_id]
        elif filename:
            # Find documents matching filename (case-insensitive, partial match)
            matching_docs = [
                doc for doc in all_docs 
                if filename.lower() in doc.get('file_name', '').lower()
            ]
        
        if not matching_docs:
            logger.warning(f"No documents found matching: {filename or doc_id}")
            return False
        
        # Delete each matching document
        for doc in matching_docs:
            doc_id_to_delete = doc.get('id')
            doc_name = doc.get('file_name', 'Unknown')
            
            logger.info(f"Deleting document: {doc_name} (ID: {doc_id_to_delete})")
            
            with document_store.driver.session() as session:
                # Delete chunks first (they have relationships)
                result = session.run("""
                    MATCH (d:SharedDocument {id: $doc_id})-[:CONTAINS]->(c:SharedChunk)
                    DELETE c
                    RETURN count(c) as deleted_chunks
                """, doc_id=doc_id_to_delete)
                deleted_chunks = result.single()["deleted_chunks"]
                logger.info(f"  Deleted {deleted_chunks} chunks")
                
                # Delete the document
                result = session.run("""
                    MATCH (d:SharedDocument {id: $doc_id})
                    DETACH DELETE d
                    RETURN count(d) as deleted_docs
                """, doc_id=doc_id_to_delete)
                deleted_docs = result.single()["deleted_docs"]
                
                if deleted_docs > 0:
                    logger.info(f"  ✓ Successfully deleted document: {doc_name}")
                else:
                    logger.warning(f"  ✗ Failed to delete document: {doc_name}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error deleting document: {e}", exc_info=True)
        return False
    finally:
        document_store.close()

def main():
    parser = argparse.ArgumentParser(description="Delete a shared document by filename or ID")
    parser.add_argument("--filename", type=str, help="Filename to delete (partial match)")
    parser.add_argument("--doc-id", type=str, help="Document ID to delete")
    parser.add_argument("--list", action="store_true", help="List all shared documents first")
    
    args = parser.parse_args()
    
    if args.list:
        logger.info("=" * 60)
        logger.info("Current Shared Documents:")
        logger.info("=" * 60)
        document_store = DocumentStore()
        try:
            docs = document_store.get_all_shared_documents()
            if docs:
                for i, doc in enumerate(docs, 1):
                    logger.info(f"{i}. {doc.get('file_name', 'Unknown')}")
                    logger.info(f"   ID: {doc.get('id', 'N/A')}")
                    logger.info(f"   Chunks: {doc.get('chunk_count', 0)}")
            else:
                logger.info("No shared documents found.")
        finally:
            document_store.close()
        logger.info("=" * 60)
        return
    
    if not args.filename and not args.doc_id:
        parser.print_help()
        return
    
    success = delete_shared_document(filename=args.filename, doc_id=args.doc_id)
    
    if success:
        logger.info("\n✅ Document deletion complete!")
    else:
        logger.error("\n❌ Document deletion failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()

