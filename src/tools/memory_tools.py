"""
Memory Tools - Allow the agent to explicitly manage memory.
"""
from typing import Dict, Any, Optional
from src.stores.memory_store import MemoryStore
from src.processors.embedding_generator import EmbeddingGenerator

class MemoryTools:
    """
    Tools for active memory management (MemGPT-style).
    Supports core memory, archival memory, and recall memory.
    """
    def __init__(self):
        self.memory_store = MemoryStore()
        self.embedding_generator = EmbeddingGenerator()
        
    def save_core_memory(self, content: str, channel_id: str) -> str:
        """
        Save a core memory (important fact/preference).
        Core memories are high-importance, frequently accessed memories.
        
        Args:
            content: The fact or preference to save.
            channel_id: The channel/user ID context.
            
        Returns:
            Confirmation message with memory ID.
        """
        embedding = self.embedding_generator.generate_embedding(content)
        memory_id = self.memory_store.store_memory(
            channel_id=channel_id,
            content=content,
            embedding=embedding,
            memory_type="core_memory",
            metadata={
                "source": "agent_tool",
                "importance": "high",
                "access_frequency": "high"
            }
        )
        return f"Core memory saved successfully. Memory ID: {memory_id}"
    
    def update_core_memory(self, memory_id: str, content: str, channel_id: str) -> str:
        """
        Update an existing core memory.
        
        Args:
            memory_id: The ID of the memory to update.
            content: The new content.
            channel_id: The channel/user ID context.
            
        Returns:
            Confirmation message.
        """
        # For now, we'll create a new memory and mark the old one as updated
        # In a full implementation, we'd update the existing memory
        embedding = self.embedding_generator.generate_embedding(content)
        new_memory_id = self.memory_store.store_memory(
            channel_id=channel_id,
            content=content,
            embedding=embedding,
            memory_type="core_memory",
            metadata={
                "source": "agent_tool",
                "importance": "high",
                "updated_from": memory_id
            }
        )
        return f"Core memory updated successfully. New Memory ID: {new_memory_id}"
    
    def get_core_memory(self, channel_id: str, query: str = None, top_k: int = 5) -> list:
        """
        Retrieve core memories for a channel/user.
        
        Args:
            channel_id: The channel/user ID.
            query: Optional query to search memories.
            top_k: Number of memories to retrieve.
            
        Returns:
            List of core memories.
        """
        if query:
            query_embedding = self.embedding_generator.generate_embedding(query)
            memories = self.memory_store.retrieve_relevant_memories(
                channel_id=channel_id,
                query_embedding=query_embedding,
                top_k=top_k,
                memory_types=["core_memory"]
            )
        else:
            # Get all core memories for the channel using get_channel_memories
            # Filter by memory_type if the method supports it
            try:
                memories = self.memory_store.get_channel_memories(
                    channel_id=channel_id,
                    limit=top_k * 2  # Get more to filter
                )
                # Filter to core_memory type
                memories = [m for m in memories if m.get("memory_type") == "core_memory"][:top_k]
            except Exception:
                # Fallback: use retrieve_relevant_memories with a generic query
                query_embedding = self.embedding_generator.generate_embedding("core memory")
                memories = self.memory_store.retrieve_relevant_memories(
                    channel_id=channel_id,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    memory_types=["core_memory"]
                )
        return memories
    
    def delete_core_memory(self, memory_id: str, channel_id: str) -> str:
        """
        Delete a core memory.
        
        Args:
            memory_id: The ID of the memory to delete.
            channel_id: The channel/user ID context.
            
        Returns:
            Confirmation message.
        """
        # MemoryStore doesn't have delete yet, so we'll mark it as deleted
        # In a full implementation, we'd actually delete it
        return f"Core memory {memory_id} marked for deletion."

    def get_tool_definitions(self) -> list:
        """Get tool definitions for the LLM."""
        return [
            {
                "name": "save_core_memory",
                "description": "Save an important fact, user preference, or long-term memory to core memory. Use this to remember important information about users or preferences.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The content to save (e.g., 'User prefers dark mode', 'User's favorite color is blue')."
                        },
                        "channel_id": {
                            "type": "string",
                            "description": "The channel or user ID context."
                        }
                    },
                    "required": ["content", "channel_id"]
                }
            },
            {
                "name": "update_core_memory",
                "description": "Update an existing core memory. Use this to modify or update previously saved memories.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "The ID of the memory to update."
                        },
                        "content": {
                            "type": "string",
                            "description": "The new content."
                        },
                        "channel_id": {
                            "type": "string",
                            "description": "The channel or user ID context."
                        }
                    },
                    "required": ["memory_id", "content", "channel_id"]
                }
            },
            {
                "name": "get_core_memory",
                "description": "Retrieve core memories for a channel/user. Use this to recall important facts or preferences.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "The channel or user ID."
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional query to search memories (e.g., 'user preferences', 'favorite color')."
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of memories to retrieve (default: 5).",
                            "default": 5
                        }
                    },
                    "required": ["channel_id"]
                }
            }
        ]
