"""
Clean up irrelevant memories that mention deleted documents or contain outdated information.
"""
import sys
from memory_store import MemoryStore
from logger_config import logger

def cleanup_irrelevant_memories():
    """Remove memories that mention deleted documents or are irrelevant."""
    logger.info("=" * 60)
    logger.info("Cleaning Up Irrelevant Memories")
    logger.info("=" * 60)
    
    memory_store = MemoryStore()
    
    try:
        channels = memory_store.get_all_channels()
        logger.info(f"\nChecking {len(channels)} channels for irrelevant memories...\n")
        
        deleted_docs = [
            "CrowdStrike2025ThreatHuntingReport.pdf",
            "My_Deezer_Library.CSV",
            "kohya-ss-gui_logs5.txt",
            "build-logs-22475bd2"
        ]
        
        total_deleted = 0
        
        for channel_id in channels:
            try:
                memories = memory_store.get_all_memories(channel_id, limit=1000)
                
                for memory in memories:
                    content = memory.get('content', '')
                    memory_id = memory.get('id', '')
                    
                    # Check if memory mentions deleted documents
                    should_delete = False
                    reason = ""
                    
                    for doc in deleted_docs:
                        if doc.lower() in content.lower():
                            should_delete = True
                            reason = f"Mentions deleted document: {doc}"
                            break
                    
                    # Check if memory is about documents when it shouldn't be
                    if not should_delete and 'god_mode_ai' in content.lower() and 'document' in content.lower():
                        # Check if it's a bot response saying the document doesn't exist
                        if 'no' in content.lower() and ('document' in content.lower() or 'file' in content.lower()):
                            should_delete = True
                            reason = "Bot response about non-existent document"
                    
                    if should_delete:
                        try:
                            # Delete the memory
                            with memory_store.driver.session() as session:
                                result = session.run(
                                    "MATCH (m:Memory {id: $memory_id}) DETACH DELETE m RETURN count(m) as deleted",
                                    memory_id=memory_id
                                )
                                deleted_count = result.single()["deleted"]
                                if deleted_count > 0:
                                    total_deleted += 1
                                    logger.info(f"  ✓ Deleted memory: {reason}")
                                    logger.info(f"    Preview: {content[:150]}...")
                        except Exception as e:
                            logger.error(f"  ✗ Error deleting memory {memory_id}: {e}")
                            
            except Exception as e:
                logger.error(f"Error processing channel {channel_id}: {e}")
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Summary: Deleted {total_deleted} irrelevant memories")
        logger.info(f"{'=' * 60}")
        
    finally:
        memory_store.close()

if __name__ == "__main__":
    cleanup_irrelevant_memories()

