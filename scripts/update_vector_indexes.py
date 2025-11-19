"""
Script to update Neo4j and Elasticsearch vector indexes to 768 dimensions.
Run this after upgrading to BGE embedding model.
"""
import sys
import os
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, ELASTICSEARCH_ENABLED
from logger_config import logger

def update_neo4j_index():
    """Update Neo4j vector index to 768 dimensions."""
    print("=" * 60)
    print("Updating Neo4j Vector Index")
    print("=" * 60)
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session() as session:
            # Check current index
            print("\nChecking existing indexes...")
            result = session.run("SHOW INDEXES")
            indexes = list(result)
            
            existing_index = None
            for record in indexes:
                if 'document_embeddings' in str(record.get('name', '')):
                    existing_index = record.get('name')
                    print(f"   Found index: {existing_index}")
            
            # Drop old index if exists
            if existing_index:
                print(f"\nDropping old index: {existing_index}")
                try:
                    session.run(f"DROP INDEX {existing_index} IF EXISTS")
                    print("   ✅ Old index dropped")
                except Exception as e:
                    print(f"   ⚠️  Error dropping index: {e}")
            
            # Create new index with 768 dimensions
            print("\nCreating new vector index with 768 dimensions...")
            try:
                session.run("""
                    CALL db.index.vector.createNodeIndex(
                        'document_embeddings',
                        'Chunk',
                        'embedding',
                        768,
                        'cosine'
                    )
                """)
                print("   ✅ New index created successfully!")
                
                # Verify
                result = session.run("SHOW INDEXES")
                for record in result:
                    if 'document_embeddings' in str(record.get('name', '')):
                        print(f"\n   Verified index: {record.get('name')}")
                        print(f"   Type: {record.get('type')}")
                        break
                
            except Exception as e:
                if "already exists" in str(e).lower():
                    print("   ⚠️  Index already exists (this is OK)")
                else:
                    raise
        
        driver.close()
        print("\n✅ Neo4j vector index updated successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error updating Neo4j index: {e}")
        import traceback
        traceback.print_exc()
        return False


def update_elasticsearch_index():
    """Update Elasticsearch index to 768 dimensions."""
    if not ELASTICSEARCH_ENABLED:
        print("\n⚠️  Elasticsearch is not enabled. Skipping.")
        return True
    
    print("\n" + "=" * 60)
    print("Updating Elasticsearch Index")
    print("=" * 60)
    
    try:
        from src.stores.elasticsearch_store import ElasticsearchStore
        
        print("\nConnecting to Elasticsearch...")
        es_store = ElasticsearchStore()
        
        # Delete old index
        index_name = es_store.chunk_index_name
        print(f"\nDeleting old index: {index_name}")
        try:
            if es_store.client.indices.exists(index=index_name):
                es_store.client.indices.delete(index=index_name)
                print("   ✅ Old index deleted")
            else:
                print("   ℹ️  Index doesn't exist (will be created)")
        except Exception as e:
            print(f"   ⚠️  Error deleting index: {e}")
        
        # Create new index with 768 dimensions
        print(f"\nCreating new index with 768 dimensions...")
        es_store._create_index()  # This will create with current config (768 dims)
        print("   ✅ New index created!")
        
        print("\n✅ Elasticsearch index updated successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error updating Elasticsearch index: {e}")
        print("   You may need to manually recreate the index")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Update all vector indexes."""
    print("\n" + "=" * 60)
    print("Vector Index Update Script")
    print("=" * 60)
    print("\nThis script will:")
    print("  1. Update Neo4j vector index to 768 dimensions")
    print("  2. Update Elasticsearch index to 768 dimensions (if enabled)")
    print("\n⚠️  WARNING: This will delete existing indexes!")
    print("   Make sure you're ready to re-embed documents.")
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Cancelled.")
        return
    
    results = []
    results.append(("Neo4j", update_neo4j_index()))
    results.append(("Elasticsearch", update_elasticsearch_index()))
    
    print("\n" + "=" * 60)
    print("Update Summary")
    print("=" * 60)
    
    for name, success in results:
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {status}: {name}")
    
    all_success = all(result for _, result in results)
    
    if all_success:
        print("\n✅ All indexes updated!")
        print("\nNext steps:")
        print("  1. Update .env file: EMBEDDING_MODEL=BAAI/bge-base-en-v1.5")
        print("  2. Re-embed your documents:")
        print("     python main.py ingest --path <your_documents>")
    else:
        print("\n⚠️  Some updates failed. Check errors above.")
    
    print("=" * 60)


if __name__ == "__main__":
    main()

