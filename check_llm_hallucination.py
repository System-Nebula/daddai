"""
Check if the LLM is hallucinating document names by examining recent responses.
This script helps identify if the bot is making up document names.
"""
from memory_store import MemoryStore
from logger_config import logger
import re

def check_for_hallucinated_documents():
    """Check memories for mentions of documents that don't exist."""
    logger.info("=" * 60)
    logger.info("Checking for Hallucinated Document References")
    logger.info("=" * 60)
    
    # Known documents that actually exist
    real_documents = [
        "God_Mode_AI_Prompt__The_Ultimate_Jailbreak_and_Sys.md",
        "Project_Todo_List__RunPod_ComfyUI__IndexTTS2-Maya_TTS.md"
    ]
    
    # Documents the user says the bot mentioned but don't exist
    hallucinated_docs = [
        "CrowdStrike2025ThreatHuntingReport.pdf",
        "My_Deezer_Library.CSV",
        "kohya-ss-gui_logs5.txt",
        "build-logs-22475bd2"
    ]
    
    memory_store = MemoryStore()
    
    try:
        channels = memory_store.get_all_channels()
        logger.info(f"\nChecking {len(channels)} channels for document mentions...\n")
        
        hallucination_found = False
        
        for channel_id in channels:
            try:
                memories = memory_store.get_all_memories(channel_id, limit=50)
                
                for memory in memories:
                    content = memory.get('content', '')
                    memory_type = memory.get('memory_type', '')
                    
                    # Check for mentions of hallucinated documents
                    for hallucinated_doc in hallucinated_docs:
                        if hallucinated_doc.lower() in content.lower():
                            logger.warning(f"⚠️  Found mention of non-existent document:")
                            logger.warning(f"   Channel: {channel_id}")
                            logger.warning(f"   Memory Type: {memory_type}")
                            logger.warning(f"   Document: {hallucinated_doc}")
                            logger.warning(f"   Content preview: {content[:300]}...")
                            logger.warning("")
                            hallucination_found = True
                    
                    # Also check for patterns like "The only files you've shared"
                    if re.search(r'(?:only|files?|documents?)\s+(?:you\'?ve|you have|that are|available)', content, re.IGNORECASE):
                        logger.info(f"📝 Found potential document listing:")
                        logger.info(f"   Channel: {channel_id}")
                        logger.info(f"   Content preview: {content[:400]}...")
                        logger.info("")
            except Exception as e:
                logger.debug(f"Error checking channel {channel_id}: {e}")
                        
        if not hallucination_found:
            logger.info("✅ No hallucinated document references found in memories.")
            logger.info("\n💡 If the bot is mentioning documents that don't exist,")
            logger.info("   it's likely the LLM generating them in its response,")
            logger.info("   not retrieving them from the database.")
            
    finally:
        memory_store.close()
    
    logger.info("\n" + "=" * 60)
    logger.info("Recommendation:")
    logger.info("  Update the system prompt to explicitly tell the LLM:")
    logger.info("  - Only mention documents that are in the source_documents list")
    logger.info("  - Don't make up or infer document names")
    logger.info("  - If asked about documents, check source_documents first")
    logger.info("=" * 60)

if __name__ == "__main__":
    check_for_hallucinated_documents()

