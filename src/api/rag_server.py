"""
Persistent RAG server that keeps models loaded in memory.
Communicates via stdin/stdout JSON-RPC style for fast responses.
Uses EnhancedRAGPipeline for advanced features.
"""
import json
import sys
import os
import signal

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.core.enhanced_rag_pipeline import EnhancedRAGPipeline
    USE_ENHANCED = True
except ImportError:
    # Fallback to basic pipeline if enhanced is not available
    from src.core.rag_pipeline import RAGPipeline as EnhancedRAGPipeline
    USE_ENHANCED = False

from src.memory.conversation_store import ConversationStore

class RAGServer:
    def __init__(self):
        """Initialize the persistent RAG server."""
        print("Initializing RAG server...", file=sys.stderr)
        print("Loading embedding model (this may take a moment)...", file=sys.stderr)
        
        if USE_ENHANCED:
            print("Using Enhanced RAG Pipeline with intelligent features...", file=sys.stderr)
            self.pipeline = EnhancedRAGPipeline()
        else:
            print("Using basic RAG Pipeline (enhanced not available)...", file=sys.stderr)
            from src.core.rag_pipeline import RAGPipeline
            self.pipeline = RAGPipeline()
        
        # Initialize conversation store with embedding generator for semantic search
        print("Initializing conversation store...", file=sys.stderr)
        embedding_gen = None
        if hasattr(self.pipeline, 'embedding_generator'):
            embedding_gen = self.pipeline.embedding_generator
        self.conversation_store = ConversationStore(embedding_generator=embedding_gen)
        
        print("RAG server ready!", file=sys.stderr)
        sys.stderr.flush()
    
    def handle_request(self, request):
        """Handle a JSON-RPC style request."""
        try:
            request_id = request.get('id', 0)
            method = request.get('method')
            params = request.get('params', {})
            
            if method == 'query':
                # Use channel_id if provided, otherwise fall back to user_id
                channel_id = params.get('channel_id') or params.get('user_id')
                # Disable memory when querying a specific document to avoid contamination
                doc_id = params.get('doc_id')
                doc_filename = params.get('doc_filename')
                use_memory = params.get('use_memory', True) and not doc_id and not doc_filename
                
                result = self.pipeline.query(
                    question=params.get('question', ''),
                    top_k=params.get('top_k', 10),
                    temperature=params.get('temperature', 0.7),
                    max_tokens=params.get('max_tokens', 600),  # Reduced from 800 to 600 for faster generation
                    max_context_tokens=params.get('max_context_tokens', 1500),  # Reduced from 1800 to 1500 for faster processing
                    user_id=params.get('user_id'),  # Kept for backward compat
                    channel_id=channel_id,  # New: channel-based memories
                    use_memory=use_memory,  # Disabled when querying specific document
                    use_shared_docs=params.get('use_shared_docs', True),
                    use_hybrid_search=params.get('use_hybrid_search', True),
                    use_query_expansion=params.get('use_query_expansion', True),
                    use_temporal_weighting=params.get('use_temporal_weighting', True),
                    doc_id=doc_id,  # Filter to specific document by ID
                    doc_filename=doc_filename,  # Filter to specific document by filename
                    mentioned_user_id=params.get('mentioned_user_id'),  # Pass mentioned user ID for state queries
                    is_admin=params.get('is_admin', False)  # Pass admin status for tool creation
                )
                
                response = {
                    "answer": result['answer'],
                    "context_chunks": len(result['context_chunks']),
                    "memories_used": len(result.get('memories', [])),
                    "question": result['question'],
                    "source_documents": result.get('source_documents', []),
                    "source_memories": result.get('source_memories', []),
                    "timing": result.get('timing', {}),
                    "is_casual_conversation": result.get('is_casual_conversation', False),  # Flag for conversational responses
                    "service_routing": result.get('service_routing', 'rag'),  # Indicate which service was used
                    "tool_calls": result.get('tool_calls', [])  # Include tool calls for image generation, etc.
                }
                
                return {"id": request_id, "result": response, "error": None}
            elif method == 'ping':
                return {"id": request_id, "result": {"status": "ok"}, "error": None}
            elif method == 'get_conversation':
                # Get conversation history for a user (all messages by default, or limit if specified)
                user_id = params.get('user_id')
                limit = params.get('limit')  # None = all messages
                if not user_id:
                    return {"id": request_id, "result": None, "error": "user_id required"}
                messages = self.conversation_store.get_conversation(user_id, limit)
                return {"id": request_id, "result": {"messages": messages}, "error": None}
            elif method == 'get_recent_conversation':
                # Get recent conversation messages (for context, still limited for performance)
                user_id = params.get('user_id')
                max_messages = params.get('max_messages', 5)
                days = params.get('days')  # Optional: filter by days
                if not user_id:
                    return {"id": request_id, "result": None, "error": "user_id required"}
                messages = self.conversation_store.get_recent_conversation(user_id, max_messages, days)
                return {"id": request_id, "result": {"messages": messages}, "error": None}
            elif method == 'get_conversation_stats':
                # Get conversation statistics
                user_id = params.get('user_id')
                if not user_id:
                    return {"id": request_id, "result": None, "error": "user_id required"}
                stats = self.conversation_store.get_conversation_stats(user_id)
                return {"id": request_id, "result": stats, "error": None}
            elif method == 'add_conversation':
                # Add a conversation message
                user_id = params.get('user_id')
                question = params.get('question')
                answer = params.get('answer')
                channel_id = params.get('channel_id')
                embedding = params.get('embedding')  # Optional embedding
                if not user_id or not question or not answer:
                    return {"id": request_id, "result": None, "error": "user_id, question, and answer required"}
                message_id = self.conversation_store.add_message(user_id, question, answer, channel_id, embedding)
                return {"id": request_id, "result": {"message_id": message_id}, "error": None}
            elif method == 'get_relevant_conversations':
                # Get semantically relevant conversations
                user_id = params.get('user_id')
                query = params.get('query', '')
                query_embedding = params.get('query_embedding')
                top_k = params.get('top_k', 5)
                if not user_id:
                    return {"id": request_id, "result": None, "error": "user_id required"}
                if not query_embedding and hasattr(self.pipeline, 'embedding_generator'):
                    # Generate embedding if not provided
                    try:
                        query_embedding = self.pipeline.embedding_generator.generate_embedding(query)
                    except:
                        query_embedding = None
                messages = self.conversation_store.get_relevant_conversations(user_id, query, query_embedding or [], top_k)
                return {"id": request_id, "result": {"messages": messages}, "error": None}
            elif method == 'clear_conversation':
                # Clear conversation history for a user
                user_id = params.get('user_id')
                if not user_id:
                    return {"id": request_id, "result": None, "error": "user_id required"}
                success = self.conversation_store.clear_conversation(user_id)
                return {"id": request_id, "result": {"success": success}, "error": None}
            else:
                return {"id": request_id, "result": None, "error": f"Unknown method: {method}"}
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"Error handling request: {error_msg}", file=sys.stderr)
            return {"id": request.get('id', 0), "result": None, "error": str(e)}
    
    def run(self):
        """Run the server loop."""
        # Handle graceful shutdown
        def cleanup_handler(sig, frame):
            print("\nCleaning up and shutting down RAG server...", file=sys.stderr)
            try:
                self.conversation_store.close()
            except:
                pass
            try:
                self.pipeline.close()
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
                error_response = {"result": None, "error": f"Invalid JSON: {str(e)}"}
                print(json.dumps(error_response), file=sys.stdout)
                sys.stdout.flush()
            except Exception as e:
                error_response = {"result": None, "error": str(e)}
                print(json.dumps(error_response), file=sys.stdout)
                sys.stdout.flush()

if __name__ == "__main__":
    server = RAGServer()
    server.run()

