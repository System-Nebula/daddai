"""
Memory compression module to summarize and consolidate old memories.
Reduces storage usage and improves retrieval context by condensing history.
"""
from typing import List, Dict, Any, Optional
import time
from datetime import datetime
from logger_config import logger
from src.stores.memory_store import MemoryStore
from src.clients.openai_compatible_client import OpenAICompatibleClient
from src.processors.embedding_generator import EmbeddingGenerator

class MemoryCompressor:
    """Compresses old memories into summaries."""
    
    def __init__(self, memory_store: MemoryStore, llm_client: OpenAICompatibleClient):
        """
        Initialize memory compressor.
        
        Args:
            memory_store: Store to access memories
            llm_client: Client for generating summaries
        """
        self.memory_store = memory_store
        self.llm_client = llm_client
        self.embedding_generator = EmbeddingGenerator()
        
    def compress_channel_memories(self, 
                                 channel_id: str, 
                                 threshold: int = 50, 
                                 batch_size: int = 10) -> Dict[str, Any]:
        """
        Compress memories for a specific channel if they exceed threshold.
        
        Args:
            channel_id: Channel ID to process
            threshold: Minimum number of memories to trigger compression
            batch_size: Number of oldest memories to compress at once
            
        Returns:
            Dict with results (compressed_count, new_memory_id)
        """
        # 1. Get all memories for the channel
        # We use a large limit to get the count
        memories = self.memory_store.get_channel_memories(channel_id=channel_id, limit=1000)
        
        if len(memories) < threshold:
            return {"status": "skipped", "reason": "below_threshold", "count": len(memories)}
        
        # 2. Sort by date (oldest first)
        # created_at is a string, so we rely on ISO format sorting or parsing
        # Neo4j returns ISO strings which sort correctly lexicographically
        memories.sort(key=lambda x: x.get('created_at', ''))
        
        # 3. Select oldest batch to compress
        # Filter out existing summaries to avoid re-compressing summaries repeatedly
        # (unless we want hierarchical summarization, which is more complex)
        raw_memories = [m for m in memories if m.get('memory_type') != 'summary']
        
        if len(raw_memories) < batch_size:
             return {"status": "skipped", "reason": "not_enough_raw_memories"}
             
        to_compress = raw_memories[:batch_size]
        
        # 4. Generate Summary
        summary_text = self._generate_summary(to_compress)
        
        if not summary_text:
            logger.warning(f"Failed to generate summary for channel {channel_id}")
            return {"status": "failed", "reason": "generation_failed"}
            
        # 5. Create new memory
        # Generate embedding for summary
        summary_embedding = self.embedding_generator.generate_embedding(summary_text)
        
        # Store new summary memory
        new_memory_id = self.memory_store.store_memory(
            channel_id=channel_id,
            content=summary_text,
            embedding=summary_embedding,
            memory_type="summary",
            metadata={
                "compressed_count": len(to_compress),
                "date_range": f"{to_compress[0].get('created_at')} to {to_compress[-1].get('created_at')}",
                "original_ids": [m.get('id') for m in to_compress if m.get('id')] # Note: get_channel_memories might not return IDs, need to check
            }
        )
        
        # 6. Delete old memories
        deleted_count = 0
        for memory in to_compress:
            memory_id = memory.get('id')
            if memory_id:
                try:
                    self.memory_store.delete_memory(memory_id)
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete memory {memory_id}: {e}")
        
        logger.info(f"Compressed {len(to_compress)} memories into 1 summary for channel {channel_id}")
        
        return {
            "status": "success",
            "compressed_count": len(to_compress),
            "deleted_count": deleted_count,
            "new_memory_id": new_memory_id,
            "summary": summary_text[:100] + "..."
        }

    def _generate_summary(self, memories: List[Dict[str, Any]]) -> str:
        """Generate a summary of the provided memories."""
        context_text = "\n".join([f"- [{m.get('created_at', '?')}] {m.get('content')}" for m in memories])
        
        system_prompt = "You are a memory consolidator. Summarize the following conversation history into a single, concise, information-dense memory."
        user_prompt = f"""Summarize these conversation fragments into a single coherent memory paragraph. 
Preserve key facts, user preferences, and important context. 
Discard trivial chitchat.

Conversation History:
{context_text}

Summary:"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return self.llm_client.generate_response(messages, temperature=0.3, max_tokens=300)
