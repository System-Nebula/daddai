"""
Script to clear memories and conversations from Neo4j.
Allows selective clearing of different data types.
"""
import sys
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from logger_config import logger

def clear_memories_and_conversations(clear_memories=True, clear_conversations=True, clear_user_state=False, clear_items=False, skip_confirmation=False):
    """
    Clear memories and conversations from Neo4j.
    
    Args:
        clear_memories: Clear all Memory nodes
        clear_conversations: Clear all ConversationMessage nodes
        clear_user_state: Clear user state (gold, inventory, etc.)
        clear_items: Clear item tracking data
        skip_confirmation: Skip confirmation prompt (for non-interactive use)
    """
    driver = None
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        logger.warning("=" * 60)
        logger.warning("CLEARING DATA FROM NEO4J")
        logger.warning("=" * 60)
        
        if clear_memories:
            logger.warning("  ✓ Will delete: All Memory nodes")
        if clear_conversations:
            logger.warning("  ✓ Will delete: All ConversationMessage nodes")
        if clear_user_state:
            logger.warning("  ✓ Will delete: All user state (gold, inventory, etc.)")
        if clear_items:
            logger.warning("  ✓ Will delete: All Item nodes and relationships")
        
        logger.warning("  ⚠  Will NOT delete: Documents, Chunks, User nodes, Relationships")
        logger.warning("=" * 60)
        
        if not skip_confirmation:
            confirmation = input("\nType 'yes' to confirm: ")
            
            if confirmation.lower() != 'yes':
                logger.info("Operation cancelled.")
                return
        else:
            logger.info("\nSkipping confirmation (--yes flag used)")
        
        with driver.session() as session:
            logger.info("\nStarting data deletion...")
            total_deleted = 0
            
            # Clear memories
            if clear_memories:
                logger.info("Deleting Memory nodes...")
                result = session.run("MATCH (m:Memory) DETACH DELETE m RETURN count(m) as deleted")
                deleted = result.single()["deleted"]
                logger.info(f"  ✓ Deleted {deleted} Memory nodes")
                total_deleted += deleted
            
            # Clear conversations
            if clear_conversations:
                logger.info("Deleting ConversationMessage nodes...")
                result = session.run("MATCH (m:ConversationMessage) DETACH DELETE m RETURN count(m) as deleted")
                deleted = result.single()["deleted"]
                logger.info(f"  ✓ Deleted {deleted} ConversationMessage nodes")
                total_deleted += deleted
            
            # Clear user state (stored as properties on User nodes)
            if clear_user_state:
                logger.info("Clearing user state properties...")
                result = session.run("""
                    MATCH (u:User)
                    REMOVE u.gold, u.inventory, u.level, u.state
                    RETURN count(u) as updated
                """)
                updated = result.single()["updated"]
                logger.info(f"  ✓ Cleared state from {updated} User nodes")
            
            # Clear items
            if clear_items:
                logger.info("Deleting Item nodes...")
                result = session.run("MATCH (i:Item) DETACH DELETE i RETURN count(i) as deleted")
                deleted = result.single()["deleted"]
                logger.info(f"  ✓ Deleted {deleted} Item nodes")
                total_deleted += deleted
                
                # Also clear item relationships
                result = session.run("MATCH ()-[r:OWNS|HAS_ITEM|TRANSFERRED_TO|TRANSFERRED_FROM]-() DELETE r RETURN count(r) as deleted")
                deleted = result.single()["deleted"]
                logger.info(f"  ✓ Deleted {deleted} item relationships")
            
            logger.info(f"\n✅ Successfully cleared data! Total nodes deleted: {total_deleted}")
            logger.info("\nNote: Restart the Discord bot and RAG server to clear in-memory caches.")
            
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        raise
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clear memories and conversations from Neo4j")
    parser.add_argument("--memories", action="store_true", default=True, help="Clear memories (default: True)")
    parser.add_argument("--no-memories", dest="memories", action="store_false", help="Don't clear memories")
    parser.add_argument("--conversations", action="store_true", default=True, help="Clear conversations (default: True)")
    parser.add_argument("--no-conversations", dest="conversations", action="store_false", help="Don't clear conversations")
    parser.add_argument("--user-state", action="store_true", help="Also clear user state (gold, inventory, etc.)")
    parser.add_argument("--items", action="store_true", help="Also clear item tracking data")
    parser.add_argument("--all", action="store_true", help="Clear everything (memories, conversations, state, items)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    if args.all:
        clear_memories_and_conversations(
            clear_memories=True,
            clear_conversations=True,
            clear_user_state=True,
            clear_items=True,
            skip_confirmation=args.yes
        )
    else:
        clear_memories_and_conversations(
            clear_memories=args.memories,
            clear_conversations=args.conversations,
            clear_user_state=args.user_state,
            clear_items=args.items,
            skip_confirmation=args.yes
        )

