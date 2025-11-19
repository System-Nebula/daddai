#!/usr/bin/env python3
"""
Script to update Elasticsearch memory index from 384 to 768 dimensions.

This script:
1. Deletes the old memory_chunks index (384 dims)
2. Creates a new index with 768 dimensions
3. Note: Existing memory documents in Elasticsearch will be lost, but they're also in Neo4j

Usage:
    python scripts/update_elasticsearch_memory_index.py
"""
import sys
import io
from pathlib import Path

# Set UTF-8 encoding for Windows console compatibility
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass  # If it fails, continue with default encoding

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import ELASTICSEARCH_ENABLED, EMBEDDING_DIMENSION
from logger_config import logger


def update_elasticsearch_memory_index():
    """Update Elasticsearch memory index to 768 dimensions."""
    if not ELASTICSEARCH_ENABLED:
        print("\n⚠️  Elasticsearch is not enabled. Skipping.")
        return True
    
    print("\n" + "=" * 70)
    print("Update Elasticsearch Memory Index")
    print("=" * 70)
    print(f"Target dimension: {EMBEDDING_DIMENSION}")
    print("\n[WARNING] This will delete the existing memory_chunks index!")
    print("   Memory data in Neo4j will NOT be affected.")
    print("   Only Elasticsearch search index will be recreated.")
    print("=" * 70)
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Cancelled.")
        return False
    
    try:
        from elasticsearch import Elasticsearch
        from config import (
            ELASTICSEARCH_HOST, ELASTICSEARCH_PORT, ELASTICSEARCH_USER,
            ELASTICSEARCH_PASSWORD, ELASTICSEARCH_USE_SSL, ELASTICSEARCH_VERIFY_CERTS
        )
        
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
        
        # Test connection
        es_client.info()
        print("\n✅ Connected to Elasticsearch")
        
        index_name = "memory_chunks"
        
        # Check if index exists
        if es_client.indices.exists(index=index_name):
            print(f"\n📋 Found existing index: {index_name}")
            
            # Get current mapping to show dimension
            try:
                mapping = es_client.indices.get_mapping(index=index_name)
                if index_name in mapping:
                    props = mapping[index_name].get("mappings", {}).get("properties", {})
                    emb_props = props.get("embedding", {})
                    current_dims = emb_props.get("dims", "unknown")
                    print(f"   Current embedding dimension: {current_dims}")
            except Exception as e:
                print(f"   Could not read current mapping: {e}")
            
            # Delete old index
            print(f"\n🗑️  Deleting old index: {index_name}")
            es_client.indices.delete(index=index_name)
            print("   ✅ Old index deleted")
        else:
            print(f"\nℹ️  Index {index_name} doesn't exist (will be created)")
        
        # Create new index with 768 dimensions
        print(f"\n🔨 Creating new index with {EMBEDDING_DIMENSION} dimensions...")
        
        memory_mapping = {
            "mappings": {
                "properties": {
                    "chunk_id": {"type": "keyword"},
                    "doc_id": {"type": "keyword"},  # memory_id
                    "channel_id": {"type": "keyword"},
                    "text": {
                        "type": "text",
                        "analyzer": "standard",
                        "fields": {
                            "english": {
                                "type": "text",
                                "analyzer": "english"
                            }
                        }
                    },
                    "memory_type": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": EMBEDDING_DIMENSION,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "user_id": {"type": "keyword"},
                    "mentioned_user_id": {"type": "keyword"},
                    "created_at": {"type": "date"}
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        }
        
        es_client.indices.create(
            index=index_name,
            **memory_mapping
        )
        print(f"   ✅ New index created with {EMBEDDING_DIMENSION} dimensions!")
        
        # Verify the index was created correctly
        mapping = es_client.indices.get_mapping(index=index_name)
        if index_name in mapping:
            props = mapping[index_name].get("mappings", {}).get("properties", {})
            emb_props = props.get("embedding", {})
            actual_dims = emb_props.get("dims", "unknown")
            print(f"\n✅ Verified: Index now has {actual_dims} dimensions")
        
        print("\n" + "=" * 70)
        print("✅ Elasticsearch memory index updated successfully!")
        print("=" * 70)
        print("\nNote: New memories will be automatically indexed in Elasticsearch")
        print("      when they are stored. Old memories are still in Neo4j.")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error updating Elasticsearch index: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = update_elasticsearch_memory_index()
    sys.exit(0 if success else 1)

