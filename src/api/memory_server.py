#!/usr/bin/env python3
"""
Persistent Memory server that keeps memory store and embedding generator loaded in memory.
Communicates via stdin/stdout JSON-RPC style for fast responses.
"""
import json
import sys
import os
import signal
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config import ELASTICSEARCH_ENABLED, USE_GPU, EMBEDDING_BATCH_SIZE
from logger_config import logger

# Try to use hybrid memory store if Elasticsearch is enabled
try:
    from src.stores.hybrid_memory_store import HybridMemoryStore
    HYBRID_MEMORY_AVAILABLE = True
except ImportError:
    HYBRID_MEMORY_AVAILABLE = False

from src.stores.memory_store import MemoryStore
from src.processors.embedding_generator import EmbeddingGenerator


def get_memory_store():
    """Get the appropriate memory store (hybrid if available, otherwise regular)."""
    if ELASTICSEARCH_ENABLED and HYBRID_MEMORY_AVAILABLE:
        try:
            return HybridMemoryStore()
        except Exception:
            return MemoryStore()
    return MemoryStore()


class MemoryServer:
    def __init__(self):
        """Initialize the persistent Memory server."""
        print("Initializing Memory server...", file=sys.stderr)
        print("Loading memory store and embedding generator (this may take a moment)...", file=sys.stderr)
        
        # Initialize memory store
        self.memory_store = get_memory_store()
        
        # Initialize embedding generator (keep in memory for fast embeddings)
        device = USE_GPU if USE_GPU != 'auto' else None
        self.embedding_generator = EmbeddingGenerator(device=device, batch_size=EMBEDDING_BATCH_SIZE)
        
        print("Memory server ready!", file=sys.stderr)
        sys.stderr.flush()
    
    def handle_request(self, request):
        """Handle a JSON-RPC style request."""
        try:
            request_id = request.get('id', 0)
            method = request.get('method')
            params = request.get('params', {})
            
            if method == 'store':
                channel_id = params.get('channel_id')
                content = params.get('content')
                if not channel_id or not content:
                    return {"id": request_id, "result": None, "error": "channel_id and content required"}
                
                # Generate embedding
                embedding = self.embedding_generator.generate_embedding(content)
                
                # Parse metadata
                metadata = params.get('metadata', {})
                if isinstance(metadata, str):
                    metadata = json.loads(metadata) if metadata else {}
                
                # Store memory
                memory_id = self.memory_store.store_memory(
                    channel_id=channel_id,
                    content=content,
                    embedding=embedding,
                    memory_type=params.get('memory_type', 'conversation'),
                    metadata=metadata,
                    channel_name=params.get('channel_name'),
                    user_id=params.get('user_id'),
                    username=params.get('username'),
                    mentioned_user_id=params.get('mentioned_user_id')
                )
                
                return {"id": request_id, "result": {"success": True, "memory_id": memory_id}, "error": None}
            
            elif method == 'get':
                channel_id = params.get('channel_id')
                channel_name = params.get('channel_name')
                limit = params.get('limit', 100)
                
                if not channel_id and not channel_name:
                    return {"id": request_id, "result": None, "error": "Must provide channel_id or channel_name"}
                
                memories = self.memory_store.get_channel_memories(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    limit=limit
                )
                
                return {"id": request_id, "result": {"memories": memories, "count": len(memories)}, "error": None}
            
            elif method == 'list-channels':
                channels = self.memory_store.get_all_channels()
                return {"id": request_id, "result": {"channels": channels}, "error": None}
            
            elif method == 'get-all':
                limit = params.get('limit', 1000)
                memories = self.memory_store.get_all_memories(limit=limit)
                return {"id": request_id, "result": {"memories": memories, "count": len(memories)}, "error": None}
            
            elif method == 'search':
                channel_id = params.get('channel_id')
                query = params.get('query')
                top_k = params.get('top_k', 5)
                mentioned_user_id = params.get('mentioned_user_id')
                
                if not channel_id or not query:
                    return {"id": request_id, "result": None, "error": "channel_id and query required"}
                
                # Generate embedding for query
                query_embedding = self.embedding_generator.generate_embedding(query)
                
                # Retrieve relevant memories
                memories = self.memory_store.retrieve_relevant_memories(
                    channel_id=channel_id,
                    query_embedding=query_embedding,
                    top_k=top_k,
                    mentioned_user_id=mentioned_user_id
                )
                
                return {"id": request_id, "result": {"memories": memories, "count": len(memories)}, "error": None}
            
            elif method == 'ping':
                return {"id": request_id, "result": {"status": "ok"}, "error": None}
            
            else:
                return {"id": request_id, "result": None, "error": f"Unknown method: {method}"}
        
        except Exception as e:
            logger.error(f"Memory server error: {e}", exc_info=True)
            return {"id": request.get('id', 0), "result": None, "error": str(e)}
    
    def run(self):
        """Run the server loop."""
        # Handle graceful shutdown
        def cleanup_handler(sig, frame):
            print("\nCleaning up and shutting down Memory server...", file=sys.stderr)
            try:
                self.memory_store.close()
            except:
                pass
            sys.exit(0)
        
        signal.signal(signal.SIGINT, cleanup_handler)
        signal.signal(signal.SIGTERM, cleanup_handler)
        
        # Main loop: read JSON from stdin, process, write JSON to stdout
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                request = json.loads(line)
                response = self.handle_request(request)
                
                # Write response to stdout
                print(json.dumps(response), file=sys.stdout)
                sys.stdout.flush()
                
            except json.JSONDecodeError as e:
                error_response = {"id": 0, "result": None, "error": f"Invalid JSON: {str(e)}"}
                print(json.dumps(error_response), file=sys.stdout)
                sys.stdout.flush()
            except Exception as e:
                logger.error(f"Memory server loop error: {e}", exc_info=True)
                error_response = {"id": 0, "result": None, "error": str(e)}
                print(json.dumps(error_response), file=sys.stdout)
                sys.stdout.flush()


if __name__ == "__main__":
    server = MemoryServer()
    server.run()

