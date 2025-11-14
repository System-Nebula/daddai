"""
Persistent RAG server that keeps models loaded in memory.
Communicates via stdin/stdout JSON-RPC style for fast responses.
"""
import json
import sys
import signal
from rag_pipeline import RAGPipeline

class RAGServer:
    def __init__(self):
        """Initialize the persistent RAG server."""
        print("Initializing RAG server...", file=sys.stderr)
        print("Loading embedding model (this may take a moment)...", file=sys.stderr)
        
        self.pipeline = RAGPipeline()
        
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
                    doc_filename=doc_filename  # Filter to specific document by filename
                )
                
                response = {
                    "answer": result['answer'],
                    "context_chunks": len(result['context_chunks']),
                    "memories_used": len(result.get('memories', [])),
                    "question": result['question'],
                    "source_documents": result.get('source_documents', []),
                    "source_memories": result.get('source_memories', []),
                    "timing": result.get('timing', {})
                }
                
                return {"id": request_id, "result": response, "error": None}
            elif method == 'ping':
                return {"id": request_id, "result": {"status": "ok"}, "error": None}
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
        def signal_handler(sig, frame):
            print("\nShutting down RAG server...", file=sys.stderr)
            self.pipeline.close()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
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

