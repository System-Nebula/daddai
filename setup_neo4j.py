"""
Neo4j Connection Test and Setup Script
"""
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
import sys

def test_connection():
    """Test connection to Neo4j."""
    print("=" * 60)
    print("Neo4j Connection Test")
    print("=" * 60)
    print(f"\nConnecting to: {NEO4J_URI}")
    print(f"User: {NEO4J_USER}")
    print(f"Password: {'*' * len(NEO4J_PASSWORD) if NEO4J_PASSWORD else 'NOT SET'}")
    print()
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # Test connection
        with driver.session() as session:
            result = session.run("RETURN 'Neo4j is connected!' AS message, 1 + 1 AS test")
            record = result.single()
            print(f"[OK] Connection successful!")
            print(f"  Message: {record['message']}")
            print(f"  Test calculation: {record['test']}")
            
            # Check Neo4j version
            version_result = session.run("CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0] as version, edition")
            print(f"\nNeo4j Components:")
            for record in version_result:
                print(f"  - {record['name']}: {record['version']} ({record['edition']})")
        
        driver.close()
        
        print("\n" + "=" * 60)
        print("[OK] Neo4j is ready for use!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[X] Connection failed!")
        print(f"  Error: {e}")
        print("\n" + "=" * 60)
        print("Troubleshooting:")
        print("=" * 60)
        print("1. Make sure Neo4j Desktop is running")
        print("2. Make sure your database is STARTED (green status)")
        print("3. Check your .env file has the correct password")
        print("4. Default connection: bolt://localhost:7687")
        print("5. Default username: neo4j")
        print("\nTo set up your .env file:")
        print("  NEO4J_URI=bolt://localhost:7687")
        print("  NEO4J_USER=neo4j")
        print("  NEO4J_PASSWORD=your_password_here")
        return False

def initialize_database():
    """Initialize the database with required indexes and constraints."""
    print("\n" + "=" * 60)
    print("Initializing Database Schema")
    print("=" * 60)
    
    try:
        from neo4j_store import Neo4jStore
        store = Neo4jStore()
        print("[OK] Database schema initialized successfully!")
        print("  - Vector index created (or fallback enabled)")
        print("  - Constraints created")
        store.close()
        return True
    except Exception as e:
        print(f"[X] Initialization failed: {e}")
        return False

if __name__ == "__main__":
    print("\n")
    
    # Test connection
    if test_connection():
        # Initialize database schema
        print("\n")
        if initialize_database():
            print("\n[OK] Everything is set up and ready!")
            print("\nYou can now:")
            print("  1. Ingest documents: python main.py ingest --path your_documents/")
            print("  2. Query the system: python main.py query --question 'Your question'")
        else:
            print("\n[WARNING] Database initialization had issues, but connection works.")
            sys.exit(1)
    else:
        print("\n[WARNING] Please fix the connection issues before proceeding.")
        sys.exit(1)

