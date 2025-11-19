#!/usr/bin/env python3
"""
Persistent GopherAgent server that keeps the agent loaded in memory.
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

from src.agents.gopher_agent import get_gopher_agent
from logger_config import logger

class GopherAgentServer:
    def __init__(self):
        """Initialize the persistent GopherAgent server."""
        print("Initializing GopherAgent server...", file=sys.stderr)
        print("Loading GopherAgent (this may take a moment)...", file=sys.stderr)
        
        self.agent = get_gopher_agent()
        
        print("GopherAgent server ready!", file=sys.stderr)
        sys.stderr.flush()
    
    def handle_request(self, request):
        """Handle a JSON-RPC style request."""
        try:
            request_id = request.get('id', 0)
            method = request.get('method')
            params = request.get('params', {})
            
            if method == 'route_message':
                message = params.get('message', '')
                context = params.get('context', {})
                intent_result = params.get('intent_result')
                
                if intent_result:
                    result = self.agent.route_message(message, context, intent_result)
                else:
                    result = self.agent.route_message(message, context)
                
                return {"id": request_id, "result": result, "error": None}
            
            elif method == 'classify_intent':
                message = params.get('message', '')
                context = params.get('context', {})
                use_cache = params.get('use_cache', True)
                
                result = self.agent.classify_intent(message, context, use_cache=use_cache)
                
                return {"id": request_id, "result": result, "error": None}
            
            elif method == 'get_metrics':
                metrics = self.agent.get_metrics()
                return {"id": request_id, "result": metrics, "error": None}
            
            elif method == 'ping':
                return {"id": request_id, "result": {"status": "ok", "gpu_enabled": self.agent.use_gpu}, "error": None}
            
            elif method == 'clear_cache':
                self.agent.clear_cache()
                return {"id": request_id, "result": {"status": "cache_cleared"}, "error": None}
            
            elif method == 'run_agentic_task':
                message = params.get('message', '')
                context = params.get('context', {})
                
                result = self.agent.run_agentic_task(message, context)
                return {"id": request_id, "result": result, "error": None}
            
            elif method == 'should_use_agentic_mode':
                message = params.get('message', '')
                intent_result = params.get('intent_result')
                
                result = self.agent.should_use_agentic_mode(message, intent_result)
                return {"id": request_id, "result": result, "error": None}
            
            else:
                return {"id": request_id, "result": None, "error": f"Unknown method: {method}"}
        
        except Exception as e:
            logger.error(f"GopherAgent server error: {e}", exc_info=True)
            return {"id": request.get('id', 0), "result": None, "error": str(e)}
    
    def run(self):
        """Run the server loop."""
        # Handle graceful shutdown
        def cleanup_handler(sig, frame):
            print("\nCleaning up and shutting down GopherAgent server...", file=sys.stderr)
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
                error_response = {"id": 0, "result": None, "error": str(e)}
                print(json.dumps(error_response), file=sys.stdout)
                sys.stdout.flush()

if __name__ == "__main__":
    server = GopherAgentServer()
    server.run()

