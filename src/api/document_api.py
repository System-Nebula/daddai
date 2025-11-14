"""
API for document upload and management for Discord bot.
Uses HybridDocumentStore for Elasticsearch support if enabled.
"""
import json
import sys
import os
import argparse
import io

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import ELASTICSEARCH_ENABLED, USE_GPU, EMBEDDING_BATCH_SIZE, CHUNK_SIZE, CHUNK_OVERLAP

# Try to use hybrid store if Elasticsearch is enabled
try:
    from src.stores.hybrid_document_store import HybridDocumentStore
    HYBRID_STORE_AVAILABLE = True
except ImportError:
    HYBRID_STORE_AVAILABLE = False

from src.stores.document_store import DocumentStore
from src.processors.document_processor import DocumentProcessor
from src.processors.embedding_generator import EmbeddingGenerator

# Set UTF-8 encoding for stdout/stderr to handle Unicode characters on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def get_document_store():
    """Get the appropriate document store (hybrid if available, otherwise regular)."""
    if ELASTICSEARCH_ENABLED and HYBRID_STORE_AVAILABLE:
        try:
            return HybridDocumentStore()
        except Exception:
            return DocumentStore()
    return DocumentStore()


def main():
    parser = argparse.ArgumentParser(description='Document API for Discord bot')
    parser.add_argument('--action', type=str, required=True, choices=['upload', 'list', 'get-chunks', 'find-relevant'])
    parser.add_argument('--user-id', type=str, help='Discord user ID')
    parser.add_argument('--file-path', type=str, help='Path to file')
    parser.add_argument('--file-name', type=str, help='Original file name')
    parser.add_argument('--doc-id', type=str, help='Document ID for get-chunks action')
    parser.add_argument('--limit', type=int, default=100, help='Limit number of chunks to return (default: 100, max: 500)')
    parser.add_argument('--query', type=str, help='Query text for find-relevant action')
    parser.add_argument('--top-k', type=int, default=3, help='Number of documents to return for find-relevant')
    
    args = parser.parse_args()
    
    try:
        document_store = get_document_store()
        
        if args.action == 'upload':
            if not args.user_id or not args.file_path:
                raise ValueError("user-id and file-path required for upload action")
            
            # Process document
            processor = DocumentProcessor(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
            document = processor.process_document(args.file_path)
            
            # Generate embeddings
            device = USE_GPU if USE_GPU != 'auto' else None
            embedding_gen = EmbeddingGenerator(device=device, batch_size=EMBEDDING_BATCH_SIZE)
            chunk_texts = [chunk['text'] for chunk in document['chunks']]
            embeddings = embedding_gen.generate_embeddings_batch(chunk_texts)
            
            # Store document
            doc_id = document_store.store_document(
                uploaded_by=args.user_id,
                document_data=document,
                embeddings=embeddings
            )
            
            response = {
                "success": True,
                "doc_id": doc_id,
                "file_name": args.file_name,
                "chunks": len(document['chunks'])
            }
            print(json.dumps(response), file=sys.stdout)
            sys.stdout.flush()
            
        elif args.action == 'list':
            documents = document_store.get_all_shared_documents()
            response = {"documents": documents, "count": len(documents)}
            print(json.dumps(response), file=sys.stdout)
            sys.stdout.flush()
        
        elif args.action == 'get-chunks':
            if not args.doc_id:
                raise ValueError("doc-id required for get-chunks action")
            
            # Limit chunks to prevent oversized JSON responses
            limit = min(args.limit, 500)  # Cap at 500 chunks max
            all_chunks = document_store.get_document_chunks(args.doc_id)
            chunks = all_chunks[:limit] if limit > 0 else all_chunks
            response = {
                "chunks": chunks, 
                "count": len(chunks),
                "total_count": len(all_chunks),
                "doc_id": args.doc_id,
                "limited": len(chunks) < len(all_chunks)
            }
            # Use ensure_ascii=False to preserve Unicode, but limit size
            print(json.dumps(response, ensure_ascii=False), file=sys.stdout)
            sys.stdout.flush()
        
        elif args.action == 'find-relevant':
            if not args.query:
                raise ValueError("query required for find-relevant action")
            
            # Generate embedding for query
            device = USE_GPU if USE_GPU != 'auto' else None
            embedding_gen = EmbeddingGenerator(device=device, batch_size=64)
            query_embedding = embedding_gen.generate_embedding(args.query)
            
            # Find relevant documents
            relevant_docs = document_store.find_relevant_documents(
                query_embedding=query_embedding,
                top_k=args.top_k,
                min_score=0.3
            )
            
            response = {"documents": relevant_docs, "count": len(relevant_docs)}
            print(json.dumps(response), file=sys.stdout)
            sys.stdout.flush()
        
        document_store.close()
        
    except Exception as e:
        error_response = {"error": str(e)}
        print(json.dumps(error_response), file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()

