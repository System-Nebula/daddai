"""
System status API to check Elasticsearch and Neo4j connectivity.
Returns JSON status information.
"""
import json
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import ELASTICSEARCH_ENABLED


def get_elasticsearch_status():
    """Check Elasticsearch connection status."""
    if not ELASTICSEARCH_ENABLED:
        return {
            "enabled": False,
            "connected": False,
            "message": "Elasticsearch is disabled"
        }
    
    try:
        from src.stores.elasticsearch_store import ElasticsearchStore
        es_store = ElasticsearchStore()
        
        # Try to get cluster info
        info = es_store.client.info()
        version = info.get('version', {}).get('number', 'unknown')
        
        # Check indices
        indices = es_store.client.indices.get_alias()
        document_index_exists = es_store.index_name in indices
        chunk_index_exists = es_store.chunk_index_name in indices
        
        # Get document count
        doc_count = 0
        chunk_count = 0
        try:
            if document_index_exists:
                doc_stats = es_store.client.count(index=es_store.index_name)
                doc_count = doc_stats.get('count', 0)
            
            if chunk_index_exists:
                chunk_stats = es_store.client.count(index=es_store.chunk_index_name)
                chunk_count = chunk_stats.get('count', 0)
        except:
            pass
        
        es_store.close()
        
        return {
            "enabled": True,
            "connected": True,
            "version": version,
            "indices": {
                "documents": {
                    "exists": document_index_exists,
                    "count": doc_count
                },
                "chunks": {
                    "exists": chunk_index_exists,
                    "count": chunk_count
                },
                "memories": {
                    "exists": "memory_chunks" in indices,
                    "count": 0  # Will be calculated if needed
                }
            },
            "message": "Elasticsearch is connected and ready"
        }
    except ImportError:
        return {
            "enabled": True,
            "connected": False,
            "message": "Elasticsearch Python client not installed"
        }
    except Exception as e:
        return {
            "enabled": True,
            "connected": False,
            "error": str(e),
            "message": f"Failed to connect to Elasticsearch: {str(e)}"
        }


def get_neo4j_status():
    """Check Neo4j connection status."""
    try:
        from src.stores.neo4j_store import Neo4jStore
        neo4j_store = Neo4jStore()
        
        # Try a simple query
        with neo4j_store.driver.session() as session:
            result = session.run("RETURN 1 as test")
            result.single()
        
        neo4j_store.close()
        
        return {
            "connected": True,
            "message": "Neo4j is connected"
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "message": f"Failed to connect to Neo4j: {str(e)}"
        }


def get_system_status():
    """Get overall system status."""
    elasticsearch_status = get_elasticsearch_status()
    neo4j_status = get_neo4j_status()
    
    return {
        "elasticsearch": elasticsearch_status,
        "neo4j": neo4j_status,
        "hybrid_mode": elasticsearch_status.get("connected", False) and neo4j_status.get("connected", False)
    }


def main():
    """Main entry point."""
    try:
        status = get_system_status()
        print(json.dumps(status, indent=2))
        sys.stdout.flush()
    except Exception as e:
        error_response = {
            "error": str(e),
            "message": "Failed to get system status"
        }
        print(json.dumps(error_response))
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()

