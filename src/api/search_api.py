"""
API for searching documents in Elasticsearch and Neo4j separately.
Allows frontend to test and compare search results from both stores.
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

from config import ELASTICSEARCH_ENABLED

# Set UTF-8 encoding for stdout/stderr to handle Unicode characters on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def search_elasticsearch(query: str, top_k: int = 10, doc_id: str = None, doc_filename: str = None):
    """Search documents in Elasticsearch only."""
    try:
        from src.stores.elasticsearch_store import ElasticsearchStore
        from src.processors.embedding_generator import EmbeddingGenerator
        from config import USE_GPU
        
        if not ELASTICSEARCH_ENABLED:
            return {"error": "Elasticsearch is not enabled"}
        
        es_store = ElasticsearchStore()
        embedding_gen = EmbeddingGenerator(device=USE_GPU if USE_GPU != 'auto' else None, batch_size=64)
        query_embedding = embedding_gen.generate_embedding(query)
        
        # Try hybrid search first, fallback to vector search
        try:
            results = es_store.hybrid_search(
                query=query,
                query_embedding=query_embedding,
                top_k=top_k,
                doc_id=doc_id,
                doc_filename=doc_filename
            )
        except Exception as e:
            # Fallback to vector search if hybrid fails
            results = es_store.vector_search(
                query_embedding=query_embedding,
                top_k=top_k,
                doc_id=doc_id,
                doc_filename=doc_filename
            )
        
        es_store.close()
        
        return {
            "store": "elasticsearch",
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        return {"error": str(e), "store": "elasticsearch"}

def search_neo4j(query: str, top_k: int = 10, doc_id: str = None, doc_filename: str = None):
    """Search documents in Neo4j only."""
    try:
        from src.stores.document_store import DocumentStore
        from src.processors.embedding_generator import EmbeddingGenerator
        from config import USE_GPU
        
        doc_store = DocumentStore()
        embedding_gen = EmbeddingGenerator(device=USE_GPU if USE_GPU != 'auto' else None, batch_size=64)
        query_embedding = embedding_gen.generate_embedding(query)
        
        results = doc_store.similarity_search_shared(
            query_embedding=query_embedding,
            top_k=top_k,
            doc_id=doc_id,
            doc_filename=doc_filename
        )
        
        doc_store.close()
        
        return {
            "store": "neo4j",
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        return {"error": str(e), "store": "neo4j"}

def main():
    parser = argparse.ArgumentParser(description='Search API for documents')
    parser.add_argument('--query', type=str, required=True, help='Search query')
    parser.add_argument('--store', type=str, required=True, choices=['elasticsearch', 'neo4j', 'both'], help='Store to search')
    parser.add_argument('--top-k', type=int, default=10, help='Number of results')
    parser.add_argument('--doc-id', type=str, default=None, help='Filter by document ID')
    parser.add_argument('--doc-filename', type=str, default=None, help='Filter by document filename')
    
    args = parser.parse_args()
    
    try:
        if args.store == 'elasticsearch':
            result = search_elasticsearch(args.query, args.top_k, args.doc_id, args.doc_filename)
        elif args.store == 'neo4j':
            result = search_neo4j(args.query, args.top_k, args.doc_id, args.doc_filename)
        else:  # both
            es_result = search_elasticsearch(args.query, args.top_k, args.doc_id, args.doc_filename)
            neo4j_result = search_neo4j(args.query, args.top_k, args.doc_id, args.doc_filename)
            result = {
                "store": "both",
                "elasticsearch": es_result,
                "neo4j": neo4j_result
            }
        
        print(json.dumps(result, ensure_ascii=False), file=sys.stdout)
        sys.stdout.flush()
        
    except Exception as e:
        error_response = {"error": str(e)}
        print(json.dumps(error_response), file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()

