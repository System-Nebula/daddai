"""
Comprehensive data cleansing script to remove ALL data and caches.
This ensures no old/stale data is retrieved in queries.
"""
import sys
import os
import argparse
from pathlib import Path
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger


def clear_neo4j_data(verify: bool = True):
    """Clear all data from Neo4j database."""
    driver = None
    try:
        logger.info("Connecting to Neo4j...")
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        
        with driver.session() as session:
            deleted_counts = {}
            
            logger.info("Starting data deletion...")
            
            # Delete all relationships first (to avoid constraint violations)
            logger.info("Deleting all relationships...")
            result = session.run("MATCH ()-[r]-() DELETE r RETURN count(r) as deleted")
            deleted_counts['relationships'] = result.single()["deleted"]
            logger.info(f"  ✓ Deleted {deleted_counts['relationships']} relationships")
            
            # Delete all SharedChunk nodes (shared documents)
            logger.info("Deleting SharedChunk nodes...")
            result = session.run("MATCH (c:SharedChunk) DELETE c RETURN count(c) as deleted")
            deleted_counts['shared_chunks'] = result.single()["deleted"]
            logger.info(f"  ✓ Deleted {deleted_counts['shared_chunks']} SharedChunk nodes")
            
            # Delete all SharedDocument nodes
            logger.info("Deleting SharedDocument nodes...")
            result = session.run("MATCH (d:SharedDocument) DELETE d RETURN count(d) as deleted")
            deleted_counts['shared_documents'] = result.single()["deleted"]
            logger.info(f"  ✓ Deleted {deleted_counts['shared_documents']} SharedDocument nodes")
            
            # Delete all Chunk nodes (personal documents)
            logger.info("Deleting Chunk nodes...")
            result = session.run("MATCH (c:Chunk) DELETE c RETURN count(c) as deleted")
            deleted_counts['chunks'] = result.single()["deleted"]
            logger.info(f"  ✓ Deleted {deleted_counts['chunks']} Chunk nodes")
            
            # Delete all Document nodes (personal documents)
            logger.info("Deleting Document nodes...")
            result = session.run("MATCH (d:Document) DELETE d RETURN count(d) as deleted")
            deleted_counts['documents'] = result.single()["deleted"]
            logger.info(f"  ✓ Deleted {deleted_counts['documents']} Document nodes")
            
            # Delete all Memory nodes
            logger.info("Deleting Memory nodes...")
            result = session.run("MATCH (m:Memory) DELETE m RETURN count(m) as deleted")
            deleted_counts['memories'] = result.single()["deleted"]
            logger.info(f"  ✓ Deleted {deleted_counts['memories']} Memory nodes")
            
            # Delete all Channel nodes
            logger.info("Deleting Channel nodes...")
            result = session.run("MATCH (c:Channel) DELETE c RETURN count(c) as deleted")
            deleted_counts['channels'] = result.single()["deleted"]
            logger.info(f"  ✓ Deleted {deleted_counts['channels']} Channel nodes")
            
            # Delete all User nodes
            logger.info("Deleting User nodes...")
            result = session.run("MATCH (u:User) DELETE u RETURN count(u) as deleted")
            deleted_counts['users'] = result.single()["deleted"]
            logger.info(f"  ✓ Deleted {deleted_counts['users']} User nodes")
            
            # Try to drop vector indexes (they will be recreated on next use)
            logger.info("Dropping vector indexes...")
            try:
                session.run("DROP INDEX document_embeddings IF EXISTS")
                logger.info("  ✓ Dropped document_embeddings index")
            except Exception as e:
                logger.warning(f"  ⚠ Could not drop document_embeddings index: {e}")
            
            try:
                session.run("DROP INDEX memory_embeddings IF EXISTS")
                logger.info("  ✓ Dropped memory_embeddings index")
            except Exception as e:
                logger.warning(f"  ⚠ Could not drop memory_embeddings index: {e}")
            
            # Verify deletion if requested
            if verify:
                logger.info("Verifying deletion...")
                verification = {}
                
                result = session.run("MATCH (c:SharedChunk) RETURN count(c) as count")
                verification['shared_chunks'] = result.single()["count"]
                
                result = session.run("MATCH (d:SharedDocument) RETURN count(d) as count")
                verification['shared_documents'] = result.single()["count"]
                
                result = session.run("MATCH (c:Chunk) RETURN count(c) as count")
                verification['chunks'] = result.single()["count"]
                
                result = session.run("MATCH (d:Document) RETURN count(d) as count")
                verification['documents'] = result.single()["count"]
                
                result = session.run("MATCH (m:Memory) RETURN count(m) as count")
                verification['memories'] = result.single()["count"]
                
                result = session.run("MATCH (c:Channel) RETURN count(c) as count")
                verification['channels'] = result.single()["count"]
                
                result = session.run("MATCH (u:User) RETURN count(u) as count")
                verification['users'] = result.single()["count"]
                
                all_zero = all(count == 0 for count in verification.values())
                
                if all_zero:
                    logger.info("  ✓ Verification passed: All data cleared")
                else:
                    logger.warning("  ⚠ Verification warning: Some data remains:")
                    for key, count in verification.items():
                        if count > 0:
                            logger.warning(f"    - {key}: {count} remaining")
            
            total_deleted = sum(deleted_counts.values())
            logger.info(f"\n✅ Data deletion complete!")
            logger.info(f"   Total items deleted: {total_deleted}")
            
            return deleted_counts
            
    except Exception as e:
        logger.error(f"Error clearing Neo4j data: {e}", exc_info=True)
        raise
    finally:
        if driver:
            driver.close()


def clear_python_cache():
    """Clear Python cache files."""
    logger.info("Clearing Python cache files...")
    
    cache_dirs = [
        Path(__file__).parent / "__pycache__",
        Path(__file__).parent / "discord-bot" / "__pycache__",
    ]
    
    cleared = 0
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                import shutil
                shutil.rmtree(cache_dir)
                cleared += 1
                logger.info(f"  ✓ Cleared {cache_dir}")
            except Exception as e:
                logger.warning(f"  ⚠ Could not clear {cache_dir}: {e}")
    
    if cleared > 0:
        logger.info(f"✓ Cleared {cleared} cache directory(ies)")
    else:
        logger.info("  No cache directories found")


def clear_discord_bot_cache():
    """Clear Discord bot cache files."""
    logger.info("Clearing Discord bot cache...")
    
    cache_paths = [
        Path(__file__).parent / "discord-bot" / "logs",
        Path(__file__).parent / "discord-bot" / "temp",
    ]
    
    cleared = 0
    for cache_path in cache_paths:
        if cache_path.exists():
            try:
                import shutil
                if cache_path.is_dir():
                    # Clear log files but keep directory
                    for file in cache_path.glob("*"):
                        if file.is_file():
                            file.unlink()
                            cleared += 1
                    logger.info(f"  ✓ Cleared files in {cache_path}")
                else:
                    cache_path.unlink()
                    cleared += 1
                    logger.info(f"  ✓ Cleared {cache_path}")
            except Exception as e:
                logger.warning(f"  ⚠ Could not clear {cache_path}: {e}")
    
    if cleared > 0:
        logger.info(f"✓ Cleared Discord bot cache")
    else:
        logger.info("  No Discord bot cache found")


def clear_rag_cache():
    """Clear RAG pipeline caches (note: in-memory caches will be cleared on restart)."""
    logger.info("Clearing RAG pipeline caches...")
    logger.info("  Note: In-memory caches (query_embedding_cache, query_result_cache)")
    logger.info("        will be cleared when the RAG pipeline is restarted.")
    logger.info("  ✓ RAG cache clearing instructions logged")


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive data cleansing script - removes ALL data and caches"
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompt (use with caution!)'
    )
    parser.add_argument(
        '--no-verify',
        action='store_true',
        help='Skip verification after deletion'
    )
    parser.add_argument(
        '--neo4j-only',
        action='store_true',
        help='Only clear Neo4j data, skip cache clearing'
    )
    parser.add_argument(
        '--cache-only',
        action='store_true',
        help='Only clear caches, skip Neo4j data'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("COMPREHENSIVE DATA CLEANSING SCRIPT")
    print("=" * 70)
    print()
    print("⚠️  WARNING: This will delete:")
    print("   - ALL documents (SharedDocument and Document)")
    print("   - ALL chunks (SharedChunk and Chunk)")
    print("   - ALL memories")
    print("   - ALL channels")
    print("   - ALL users")
    print("   - ALL relationships")
    print("   - Vector indexes")
    if not args.neo4j_only:
        print("   - Python cache files (__pycache__)")
        print("   - Discord bot logs and temp files")
    print()
    print("This action CANNOT be undone!")
    print()
    
    if not args.yes:
        confirmation = input("Type 'DELETE ALL DATA' to confirm: ")
        if confirmation != 'DELETE ALL DATA':
            logger.info("Operation cancelled.")
            print("Operation cancelled.")
            return
    
    try:
        # Clear Neo4j data
        if not args.cache_only:
            logger.info("=" * 70)
            logger.info("CLEARING NEO4J DATA")
            logger.info("=" * 70)
            deleted_counts = clear_neo4j_data(verify=not args.no_verify)
            logger.info("")
        
        # Clear caches
        if not args.neo4j_only:
            logger.info("=" * 70)
            logger.info("CLEARING CACHES")
            logger.info("=" * 70)
            clear_python_cache()
            clear_discord_bot_cache()
            clear_rag_cache()
            logger.info("")
        
        logger.info("=" * 70)
        logger.info("✅ DATA CLEANSING COMPLETE!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Restart the Discord bot to clear in-memory caches")
        logger.info("  2. Restart the RAG server to clear query caches")
        logger.info("  3. Re-upload any documents you need")
        logger.info("")
        
        print("\n✅ Data cleansing complete!")
        print("\nNote: Restart the Discord bot and RAG server to clear in-memory caches.")
        
    except Exception as e:
        logger.error(f"Error during data cleansing: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

