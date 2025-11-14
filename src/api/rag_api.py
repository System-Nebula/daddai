"""
API wrapper for RAG system to be called from Node.js Discord bot.
Returns JSON responses for easy integration.
"""
import json
import sys
import os
import argparse

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.rag_pipeline import RAGPipeline


def main():
    parser = argparse.ArgumentParser(description='RAG API for Discord bot')
    parser.add_argument('--question', type=str, required=True, help='Question to ask')
    parser.add_argument('--top-k', type=int, default=10, help='Number of chunks to retrieve')
    parser.add_argument('--user-id', type=str, default=None, help='Discord user ID (deprecated, use channel-id)')
    parser.add_argument('--channel-id', type=str, default=None, help='Discord channel ID for memory')
    parser.add_argument('--use-memory', type=str, default='true', help='Use long-term memory')
    parser.add_argument('--use-shared-docs', type=str, default='true', help='Use shared documents')
    
    args = parser.parse_args()
    
    try:
        # Initialize RAG pipeline (debug output goes to stderr, not stdout)
        pipeline = RAGPipeline()
        
        # Query the system with all optimizations enabled
        # Use channel_id if provided, otherwise fall back to user_id for backward compatibility
        channel_id = args.channel_id if args.channel_id else (args.user_id if args.user_id else None)
        result = pipeline.query(
            question=args.question,
            top_k=args.top_k,
            max_tokens=800,  # Reduced to prevent extremely long responses (Discord limit is 4000 chars)
            user_id=args.user_id,  # Kept for backward compat
            channel_id=channel_id,  # New: channel-based memories
            use_memory=args.use_memory.lower() == 'true',
            use_shared_docs=args.use_shared_docs.lower() == 'true',
            use_hybrid_search=True,  # Enable hybrid search
            use_query_expansion=True,  # Enable query expansion
            use_temporal_weighting=True  # Enable temporal weighting
        )
        
        # Return JSON response (only to stdout)
        response = {
            "answer": result['answer'],
            "context_chunks": len(result['context_chunks']),
            "memories_used": len(result.get('memories', [])),
            "question": result['question'],
            "source_documents": result.get('source_documents', []),
            "source_memories": result.get('source_memories', [])
        }
        
        # Only print JSON to stdout
        print(json.dumps(response), file=sys.stdout)
        sys.stdout.flush()
        
        pipeline.close()
        
    except Exception as e:
        error_response = {
            "error": str(e),
            "answer": "Sorry, I encountered an error processing your question."
        }
        print(json.dumps(error_response), file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()

