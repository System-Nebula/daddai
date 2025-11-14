"""
Script to clear all memories from Neo4j.
"""
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def clear_all_memories():
    """Clear all memories and user nodes."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        # Delete all memories and relationships
        result = session.run("""
            MATCH (m:Memory)
            DETACH DELETE m
        """)
        
        # Delete all user nodes
        result2 = session.run("""
            MATCH (u:User)
            DETACH DELETE u
        """)
        
        print(f"✅ Cleared all memories and user nodes")
    
    driver.close()

if __name__ == "__main__":
    print("⚠️  WARNING: This will delete ALL memories!")
    confirm = input("Type 'yes' to confirm: ")
    if confirm.lower() == 'yes':
        clear_all_memories()
    else:
        print("Cancelled.")

