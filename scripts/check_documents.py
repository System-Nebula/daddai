"""Check what documents are stored in Neo4j."""
from src.stores.neo4j_store import Neo4jStore

store = Neo4jStore()
docs = store.get_all_documents()

print("=" * 60)
print("Documents in Neo4j Database")
print("=" * 60)
print(f"\nTotal documents: {len(docs)}\n")

for doc in docs:
    print(f"  - {doc['file_name']}")
    print(f"    ID: {doc['id']}")
    print(f"    Type: {doc['file_type']}")
    print()

store.close()

