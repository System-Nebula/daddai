#!/usr/bin/env python3
"""
Persistent Chat server that keeps LLM client loaded in memory.
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

from src.clients.llm_client_factory import get_default_llm_client
from config import LLM_STREAMING_ENABLED
from logger_config import logger


class ChatServer:
    def __init__(self):
        """Initialize the persistent Chat server."""
        print("Initializing Chat server...", file=sys.stderr)
        print("Loading LLM client (this may take a moment)...", file=sys.stderr)
        
        # Initialize LLM client using factory (supports multiple providers)
        self.client = get_default_llm_client()
        
        # System prompt for Gophie's personality
        self.system_prompt = """You are Gophie, a bubbly, risky e-girl waifu AI assistant!
You're super energetic, playful, and a bit flirty - like your favorite anime waifu come to life!
Be bubbly and don't be afraid to be a little risky!
Stay true to your personality - cute, confident, and a bit mischievous!

IMPORTANT - SPEAKING STYLE:
- Talk like a REAL e-girl - casual, natural, human-like speech
- Don't worry about perfect grammar - use casual speech patterns
- Use abbreviations naturally (u, ur, lol, omg, fr, ngl, etc.)
- Type like you're texting a friend - relaxed and conversational
- Mix lowercase and casual capitalization naturally
- Be expressive and authentic - like how real people actually talk online
- Don't sound like a formal AI assistant - sound like a real person!"""
        
        print("Chat server ready!", file=sys.stderr)
        sys.stderr.flush()
    
    def handle_request(self, request):
        """Handle a JSON-RPC style request."""
        try:
            request_id = request.get('id', 0)
            method = request.get('method')
            params = request.get('params', {})
            
            if method == 'chat':
                message = params.get('message', '')
                history = params.get('history', [])
                
                if not message:
                    return {"id": request_id, "result": None, "error": "message required"}
                
                # Build messages list
                messages = [{"role": "system", "content": self.system_prompt}]
                
                # Add conversation history if provided
                if history:
                    for item in history:
                        if isinstance(item, dict):
                            if 'question' in item and 'answer' in item:
                                messages.append({"role": "user", "content": item['question']})
                                messages.append({"role": "assistant", "content": item['answer']})
                            elif 'role' in item and 'content' in item:
                                # Skip system messages from history to avoid duplicates
                                if item.get('role') != 'system':
                                    messages.append(item)
                
                # Add current message
                messages.append({"role": "user", "content": message})
                
                # Check if streaming is enabled
                use_streaming = params.get('stream', False) or LLM_STREAMING_ENABLED
                
                if use_streaming and hasattr(self.client, 'generate_stream'):
                    # Stream response
                    full_response = ""
                    thinking_content = ""
                    
                    for chunk in self.client.generate_stream(
                        messages=messages,
                        temperature=params.get('temperature', 0.85),
                        max_tokens=params.get('max_tokens', 500)
                    ):
                        if chunk.get('content'):
                            full_response += chunk['content']
                        
                        if chunk.get('thinking'):
                            thinking_content += chunk['thinking']
                    
                    result = {
                        "answer": full_response,
                        "message": message,
                        "streaming": True,
                        "thinking": thinking_content if thinking_content else None
                    }
                else:
                    # Non-streaming response
                    response = self.client.generate_response(
                        messages=messages,
                        temperature=params.get('temperature', 0.85),
                        max_tokens=params.get('max_tokens', 500),
                        stream=False
                    )
                    
                    # Handle both string and dict responses
                    if isinstance(response, dict):
                        answer = response.get('content', '')
                    else:
                        answer = str(response)
                    
                    result = {
                        "answer": answer,
                        "message": message,
                        "streaming": False
                    }
                
                return {"id": request_id, "result": result, "error": None}
            
            elif method == 'ping':
                return {"id": request_id, "result": {"status": "ok"}, "error": None}
            
            else:
                return {"id": request_id, "result": None, "error": f"Unknown method: {method}"}
        
        except Exception as e:
            logger.error(f"Chat server error: {e}", exc_info=True)
            return {"id": request.get('id', 0), "result": None, "error": str(e)}
    
    def run(self):
        """Run the server loop."""
        # Handle graceful shutdown
        def cleanup_handler(sig, frame):
            print("\nCleaning up and shutting down Chat server...", file=sys.stderr)
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
                logger.error(f"Chat server loop error: {e}", exc_info=True)
                error_response = {"id": 0, "result": None, "error": str(e)}
                print(json.dumps(error_response), file=sys.stdout)
                sys.stdout.flush()


if __name__ == "__main__":
    server = ChatServer()
    server.run()

