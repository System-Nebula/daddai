#!/usr/bin/env python3
"""
Migration script to upgrade memory embeddings from 384 to 768 dimensions.

This script:
1. Finds all memories with 384-dimension embeddings
2. Regenerates embeddings using the current 768-dim model (BAAI/bge-base-en-v1.5)
3. Updates memories in Neo4j
4. Optionally updates Elasticsearch if enabled
5. Provides progress reporting and error handling

Usage:
    python scripts/migrate_memory_embeddings.py [--dry-run] [--batch-size N] [--limit N]
"""
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
import time

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from neo4j import GraphDatabase
from config import (
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, EMBEDDING_DIMENSION,
    USE_GPU, EMBEDDING_BATCH_SIZE, ELASTICSEARCH_ENABLED
)
from src.processors.embedding_generator import EmbeddingGenerator
from logger_config import logger


class MemoryEmbeddingMigrator:
    """Migrate memory embeddings from 384 to 768 dimensions."""
    
    def __init__(self, dry_run: bool = False):
        """Initialize the migrator."""
        self.dry_run = dry_run
        self.embedding_generator = EmbeddingGenerator(
            device=USE_GPU if USE_GPU != 'auto' else None,
            batch_size=EMBEDDING_BATCH_SIZE
        )
        self.target_dimension = EMBEDDING_DIMENSION
        
        # Connect to Neo4j
        try:
            self.driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            self.driver.verify_connectivity()
            logger.info(f"✅ Connected to Neo4j at {NEO4J_URI}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Neo4j: {e}")
            raise
        
        # Check Elasticsearch if enabled
        self.elasticsearch_enabled = False
        self.es_client = None
        if ELASTICSEARCH_ENABLED:
            try:
                from elasticsearch import Elasticsearch
                from config import (
                    ELASTICSEARCH_HOST, ELASTICSEARCH_PORT, ELASTICSEARCH_USER,
                    ELASTICSEARCH_PASSWORD, ELASTICSEARCH_USE_SSL, ELASTICSEARCH_VERIFY_CERTS
                )
                
                scheme = "https" if ELASTICSEARCH_USE_SSL else "http"
                url = f"{scheme}://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"
                
                connection_params = {"request_timeout": 30}
                if ELASTICSEARCH_USE_SSL:
                    connection_params["verify_certs"] = ELASTICSEARCH_VERIFY_CERTS
                else:
                    connection_params["verify_certs"] = False
                
                if ELASTICSEARCH_USER and ELASTICSEARCH_PASSWORD:
                    connection_params["basic_auth"] = (ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD)
                
                self.es_client = Elasticsearch(url, **connection_params)
                self.es_client.info()  # Test connection
                self.elasticsearch_enabled = True
                logger.info("✅ Elasticsearch connection verified")
            except Exception as e:
                logger.warning(f"⚠️ Elasticsearch not available: {e}")
                self.elasticsearch_enabled = False
    
    def find_memories_to_migrate(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Find all memories with embeddings that don't match the target dimension.
        
        Returns:
            List of memory records with id, content, and embedding
        """
        logger.info(f"🔍 Searching for memories with non-{self.target_dimension}-dimension embeddings...")
        
        with self.driver.session() as session:
            # Get all memories with embeddings
            query = """
                MATCH (m:Memory)
                WHERE m.embedding IS NOT NULL
                RETURN m.id AS id, m.content AS content, m.embedding AS embedding,
                       m.channel_id AS channel_id, m.memory_type AS memory_type,
                       m.metadata AS metadata, m.user_id AS user_id,
                       m.username AS username, m.mentioned_user_id AS mentioned_user_id
            """
            if limit:
                query += f" LIMIT {limit}"
            
            result = session.run(query)
            memories = []
            
            for record in result:
                embedding = record.get("embedding")
                if embedding is None:
                    continue
                
                # Check dimension
                emb_dim = len(embedding) if isinstance(embedding, (list, tuple)) else 0
                if emb_dim != self.target_dimension:
                    memories.append({
                        "id": record.get("id"),
                        "content": record.get("content", ""),
                        "embedding": embedding,
                        "old_dimension": emb_dim,
                        "channel_id": record.get("channel_id"),
                        "memory_type": record.get("memory_type", "conversation"),
                        "metadata": record.get("metadata"),
                        "user_id": record.get("user_id"),
                        "username": record.get("username"),
                        "mentioned_user_id": record.get("mentioned_user_id")
                    })
            
            logger.info(f"📊 Found {len(memories)} memories to migrate")
            if memories:
                dims = {}
                for mem in memories:
                    dim = mem["old_dimension"]
                    dims[dim] = dims.get(dim, 0) + 1
                logger.info(f"   Dimension breakdown: {dims}")
            
            return memories
    
    def migrate_memory(self, memory: Dict[str, Any]) -> bool:
        """
        Migrate a single memory's embedding.
        
        Args:
            memory: Memory record with id, content, etc.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate new embedding
            content = memory["content"]
            if not content or not content.strip():
                logger.warning(f"⚠️ Skipping memory {memory['id']}: empty content")
                return False
            
            new_embedding = self.embedding_generator.generate_embedding(content)
            
            if len(new_embedding) != self.target_dimension:
                logger.error(f"❌ Generated embedding has wrong dimension: {len(new_embedding)} != {self.target_dimension}")
                return False
            
            if not self.dry_run:
                # Update in Neo4j
                with self.driver.session() as session:
                    session.run("""
                        MATCH (m:Memory {id: $memory_id})
                        SET m.embedding = $new_embedding,
                            m.migration_date = datetime()
                    """, memory_id=memory["id"], new_embedding=new_embedding)
                
                # Update in Elasticsearch if enabled
                if self.elasticsearch_enabled:
                    try:
                        # Try to update existing document (Elasticsearch 8.x API)
                        try:
                            self.es_client.update(
                                index="memory_chunks",
                                id=memory["id"],
                                doc={"embedding": new_embedding}
                            )
                        except Exception:
                            # Fallback: try with body parameter (older API)
                            self.es_client.update(
                                index="memory_chunks",
                                id=memory["id"],
                                body={"doc": {"embedding": new_embedding}}
                            )
                    except Exception as e:
                        # Memory might not exist in Elasticsearch, that's okay
                        # Check if it's a 404 (not found) - that's expected for some memories
                        error_str = str(e).lower()
                        if "404" not in error_str and "not_found" not in error_str:
                            logger.debug(f"Could not update Elasticsearch for {memory['id']}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error migrating memory {memory.get('id', 'unknown')}: {e}")
            return False
    
    def migrate_batch(self, memories: List[Dict[str, Any]], batch_size: int = 10) -> Dict[str, int]:
        """
        Migrate a batch of memories.
        
        Args:
            memories: List of memory records to migrate
            batch_size: Number of memories to process before reporting progress
            
        Returns:
            Dictionary with success_count, failure_count, skipped_count
        """
        stats = {"success": 0, "failure": 0, "skipped": 0}
        total = len(memories)
        
        logger.info(f"🚀 Starting migration of {total} memories...")
        if self.dry_run:
            logger.info("⚠️ DRY RUN MODE - No changes will be saved")
        
        start_time = time.time()
        
        for i, memory in enumerate(memories, 1):
            # Progress reporting
            if i % batch_size == 0 or i == total:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                eta = (total - i) / rate if rate > 0 else 0
                logger.info(
                    f"📈 Progress: {i}/{total} ({i*100//total}%) | "
                    f"✅ {stats['success']} | ❌ {stats['failure']} | ⏭️ {stats['skipped']} | "
                    f"ETA: {eta:.1f}s"
                )
            
            # Migrate memory
            if self.migrate_memory(memory):
                stats["success"] += 1
            else:
                stats["failure"] += 1
        
        elapsed = time.time() - start_time
        logger.info(
            f"✅ Migration complete! "
            f"✅ {stats['success']} | ❌ {stats['failure']} | ⏭️ {stats['skipped']} | "
            f"Time: {elapsed:.1f}s"
        )
        
        return stats
    
    def close(self):
        """Close connections."""
        if self.driver:
            self.driver.close()
        if self.es_client:
            self.es_client.close()


def main():
    """Main migration function."""
    parser = argparse.ArgumentParser(
        description="Migrate memory embeddings from 384 to 768 dimensions"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making changes (dry run mode)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of memories to process before reporting progress (default: 10)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of memories to migrate (for testing)"
    )
    parser.add_argument(
        "--target-dimension",
        type=int,
        default=None,
        help=f"Target embedding dimension (default: {EMBEDDING_DIMENSION})"
    )
    
    args = parser.parse_args()
    
    # Set UTF-8 encoding for Windows console compatibility
    import io
    import sys
    if sys.platform == 'win32':
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except:
            pass  # If it fails, continue with default encoding
    
    # Print banner
    print("=" * 70)
    print("Memory Embedding Migration Script")
    print("=" * 70)
    print(f"Target dimension: {args.target_dimension or EMBEDDING_DIMENSION}")
    print(f"Dry run: {args.dry_run}")
    print(f"Batch size: {args.batch_size}")
    if args.limit:
        print(f"Limit: {args.limit}")
    print("=" * 70)
    print()
    
    migrator = None
    try:
        migrator = MemoryEmbeddingMigrator(dry_run=args.dry_run)
        
        # Find memories to migrate
        memories = migrator.find_memories_to_migrate(limit=args.limit)
        
        if not memories:
            logger.info("✅ No memories need migration!")
            return 0
        
        # Confirm before proceeding (unless dry run)
        if not args.dry_run:
            response = input(f"\n⚠️  Migrate {len(memories)} memories? (yes/no): ")
            if response.lower() not in ["yes", "y"]:
                logger.info("Migration cancelled by user")
                return 0
        
        # Migrate memories
        stats = migrator.migrate_batch(memories, batch_size=args.batch_size)
        
        # Print summary (using ASCII-safe characters for Windows compatibility)
        print("\n" + "=" * 70)
        print("Migration Summary")
        print("=" * 70)
        print(f"Total processed: {len(memories)}")
        print(f"[OK] Successful: {stats['success']}")
        print(f"[FAIL] Failed: {stats['failure']}")
        print(f"[SKIP] Skipped: {stats['skipped']}")
        print("=" * 70)
        
        if stats["failure"] > 0:
            logger.warning(f"⚠️ {stats['failure']} memories failed to migrate. Check logs for details.")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Migration interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        return 1
    finally:
        if migrator:
            migrator.close()


if __name__ == "__main__":
    sys.exit(main())

