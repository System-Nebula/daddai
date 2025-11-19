
import sys
import os
import time
from typing import List, Dict, Any
from tqdm import tqdm

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from src.processors.embedding_generator import EmbeddingGenerator
from logger_config import logger

def reembed_chunks():
    """
    Fetch all chunks from Neo4j, generate new embeddings, and update them.
    This allows migrating to a new embedding model without original files.
    """
    print("=" * 60)
    print("Re-embedding Existing Chunks in Neo4j")
    print("=" * 60)
    
    # Initialize Neo4j driver
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Initialize Embedding Generator (uses config for model, so it will use BGE-base)
    print("\nInitializing Embedding Model (this may take a moment)...")
    embedding_generator = EmbeddingGenerator()
    print(f"Model loaded: {embedding_generator.model.model_name if hasattr(embedding_generator.model, 'model_name') else 'Unknown'}")
    print(f"Dimension: {embedding_generator.get_dimension()}")
    
    try:
        with driver.session() as session:
            # 1. Fetch all chunks
            print("\nFetching all chunks from database...")
            result = session.run("""
                MATCH (c:Chunk)
                WHERE c.text IS NOT NULL
                RETURN c.id AS id, c.text AS text
            """)
            
            chunks = list(result)
            total_chunks = len(chunks)
            print(f"Found {total_chunks} chunks to re-embed.")
            
            if total_chunks == 0:
                print("No chunks found. Nothing to do.")
                return
            
            # 2. Process in batches
            batch_size = 32
            updated_count = 0
            start_time = time.time()
            
            print("\nStarting re-embedding process...")
            
            # Create batches
            for i in tqdm(range(0, total_chunks, batch_size), desc="Processing batches"):
                batch = chunks[i:i + batch_size]
                
                # Extract texts
                texts = [record['text'] for record in batch]
                ids = [record['id'] for record in batch]
                
                try:
                    # Generate new embeddings
                    embeddings = embedding_generator.generate_embeddings_batch(texts)
                    
                    # Prepare update data
                    update_data = []
                    for chunk_id, embedding in zip(ids, embeddings):
                        update_data.append({
                            'id': chunk_id,
                            'embedding': embedding
                        })
                    
                    # Update in Neo4j
                    session.run("""
                        UNWIND $updates AS update
                        MATCH (c:Chunk {id: update.id})
                        SET c.embedding = update.embedding
                    """, updates=update_data)
                    
                    updated_count += len(batch)
                    
                except Exception as e:
                    print(f"\nError processing batch {i//batch_size}: {e}")
                    # Continue to next batch
                    continue
            
            duration = time.time() - start_time
            print(f"\n✅ Successfully re-embedded {updated_count}/{total_chunks} chunks.")
            print(f"Time taken: {duration:.2f} seconds")
            print(f"Average speed: {updated_count/duration:.2f} chunks/sec")
            
    except Exception as e:
        print(f"\n❌ Error during re-embedding: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.close()

if __name__ == "__main__":
    reembed_chunks()
