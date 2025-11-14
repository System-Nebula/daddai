"""
API for memory operations (store, retrieve, list) for Discord bot.
"""
import json
import sys
import argparse
from datetime import datetime
from memory_store import MemoryStore
from embedding_generator import EmbeddingGenerator
from config import USE_GPU, EMBEDDING_BATCH_SIZE


def main():
    parser = argparse.ArgumentParser(description='Memory API for Discord bot')
    parser.add_argument('--action', type=str, required=True, choices=['store', 'get', 'list-channels', 'get-all', 'search'])
    parser.add_argument('--channel-id', type=str, help='Discord channel ID')
    parser.add_argument('--channel-name', type=str, help='Discord channel name (for lookup)')
    parser.add_argument('--content', type=str, help='Memory content')
    parser.add_argument('--memory-type', type=str, default='conversation', help='Memory type')
    parser.add_argument('--metadata', type=str, default='{}', help='Metadata JSON')
    parser.add_argument('--limit', type=int, default=100, help='Limit for get action')
    parser.add_argument('--query', type=str, help='Search query for semantic search')
    parser.add_argument('--top-k', type=int, default=5, help='Number of results for search')
    parser.add_argument('--user-id', type=str, help='User ID for storing/retrieving memories')
    parser.add_argument('--username', type=str, help='Username for storing memories')
    parser.add_argument('--mentioned-user-id', type=str, help='Mentioned user ID (for facts about other users or search boost)')
    
    args = parser.parse_args()
    
    try:
        memory_store = MemoryStore()
        
        if args.action == 'store':
            if not args.channel_id or not args.content:
                raise ValueError("channel-id and content required for store action")
            
            # Generate embedding (redirect debug output to stderr)
            device = USE_GPU if USE_GPU != 'auto' else None
            embedding_gen = EmbeddingGenerator(device=device, batch_size=64)
            embedding = embedding_gen.generate_embedding(args.content)
            
            # Parse metadata
            metadata = json.loads(args.metadata) if args.metadata else {}
            
            # Store memory with channel name and user info if provided
            memory_id = memory_store.store_memory(
                channel_id=args.channel_id,
                content=args.content,
                embedding=embedding,
                memory_type=args.memory_type,
                metadata=metadata,
                channel_name=args.channel_name,
                user_id=args.user_id,
                username=args.username,
                mentioned_user_id=args.mentioned_user_id
            )
            
            response = {"success": True, "memory_id": memory_id}
            print(json.dumps(response), file=sys.stdout)
            sys.stdout.flush()
            
        elif args.action == 'get':
            # Can search by channel_id or channel_name
            if not args.channel_id and not args.channel_name:
                raise ValueError("Must provide channel-id or channel-name for get action")
            
            memories = memory_store.get_channel_memories(
                channel_id=args.channel_id,
                channel_name=args.channel_name,
                limit=args.limit
            )
            response = {"memories": memories, "count": len(memories)}
            print(json.dumps(response), file=sys.stdout)
            sys.stdout.flush()
        
        elif args.action == 'list-channels':
            channels = memory_store.get_all_channels()
            response = {"channels": channels}
            print(json.dumps(response), file=sys.stdout)
            sys.stdout.flush()
        
        elif args.action == 'get-all':
            memories = memory_store.get_all_memories(limit=args.limit)
            response = {"memories": memories, "count": len(memories)}
            print(json.dumps(response), file=sys.stdout)
            sys.stdout.flush()
        
        elif args.action == 'search':
            if not args.channel_id or not args.query:
                raise ValueError("channel-id and query required for search action")
            
            # Generate embedding for query
            device = USE_GPU if USE_GPU != 'auto' else None
            embedding_gen = EmbeddingGenerator(device=device, batch_size=64)
            query_embedding = embedding_gen.generate_embedding(args.query)
            
            # Retrieve relevant memories (boost memories mentioning the queried user if provided)
            memories = memory_store.retrieve_relevant_memories(
                channel_id=args.channel_id,
                query_embedding=query_embedding,
                top_k=args.top_k,
                mentioned_user_id=args.mentioned_user_id  # Boost memories mentioning this user
            )
            response = {"memories": memories, "count": len(memories)}
            print(json.dumps(response), file=sys.stdout)
            sys.stdout.flush()
        
        memory_store.close()
        
    except Exception as e:
        error_response = {"error": str(e)}
        print(json.dumps(error_response), file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()

