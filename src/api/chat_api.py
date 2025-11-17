"""
Simple chat API for Discord bot - supports multiple OpenAI-compatible providers.
Returns JSON responses for easy integration. Supports streaming.
"""
import json
import sys
import os
import argparse

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.clients.llm_client_factory import get_default_llm_client
from config import LLM_STREAMING_ENABLED

def main():
    parser = argparse.ArgumentParser(description='Simple Chat API for Discord bot')
    parser.add_argument('--message', type=str, required=True, help='Message to send')
    parser.add_argument('--history', type=str, default=None, help='JSON array of conversation history')
    parser.add_argument('--stream', action='store_true', help='Enable streaming (outputs chunks as they arrive)')
    
    args = parser.parse_args()
    
    try:
        # Initialize LLM client using factory (supports multiple providers)
        # This will use the provider specified in LLM_PROVIDER config
        client = get_default_llm_client()
        
        # System prompt for Gophie's personality
        system_prompt = """You are Gophie, a bubbly, risky e-girl waifu AI assistant!
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
        
        # Parse conversation history if provided
        messages = [{"role": "system", "content": system_prompt}]
        if args.history:
            try:
                history = json.loads(args.history)
                # Convert history to message format
                for item in history:
                    if isinstance(item, dict):
                        if 'question' in item and 'answer' in item:
                            messages.append({"role": "user", "content": item['question']})
                            messages.append({"role": "assistant", "content": item['answer']})
                        elif 'role' in item and 'content' in item:
                            # Skip system messages from history to avoid duplicates
                            if item.get('role') != 'system':
                                messages.append(item)
            except json.JSONDecodeError:
                pass
        
        # Add current message
        messages.append({"role": "user", "content": args.message})
        
        # Check if streaming is enabled
        use_streaming = args.stream or LLM_STREAMING_ENABLED
        
        if use_streaming and hasattr(client, 'generate_stream'):
            # Stream response
            full_response = ""
            thinking_content = ""
            
            for chunk in client.generate_stream(
                messages=messages,
                temperature=0.85,
                max_tokens=500
            ):
                if chunk.get('content'):
                    full_response += chunk['content']
                    # Output chunk immediately for real-time streaming
                    chunk_result = {
                        "chunk": chunk['content'],
                        "thinking": chunk.get('thinking'),
                        "finished": chunk.get('finish_reason') is not None
                    }
                    print(json.dumps(chunk_result), file=sys.stdout)
                    sys.stdout.flush()
                
                if chunk.get('thinking'):
                    thinking_content += chunk['thinking']
            
            # Final result
            result = {
                "answer": full_response,
                "message": args.message,
                "streaming": True,
                "thinking": thinking_content if thinking_content else None
            }
        else:
            # Non-streaming response
            print(f"[Chat API] Calling LLM with {len(messages)} messages", file=sys.stderr)
            print(f"[Chat API] Message: {args.message[:100]}...", file=sys.stderr)
            
            response = client.generate_response(
                messages=messages,
                temperature=0.85,  # Higher temperature for more creative, bubbly responses
                max_tokens=4000  # Very high for GLM-4.6 thinking model (reasoning can use 1000-2000 tokens, then needs 500-1000 for response)
            )
            
            print(f"[Chat API] Response received: {len(response) if isinstance(response, str) else 'dict'} chars", file=sys.stderr)
            if isinstance(response, str):
                print(f"[Chat API] Response preview: {response[:200]}...", file=sys.stderr)
            elif isinstance(response, dict):
                print(f"[Chat API] Response keys: {list(response.keys())}", file=sys.stderr)
                if 'content' in response:
                    print(f"[Chat API] Content: {response['content'][:200]}...", file=sys.stderr)
            
            result = {
                "answer": response if isinstance(response, str) else response.get('content', str(response)),
                "message": args.message,
                "streaming": False
            }
        
        # Output final JSON response
        print(json.dumps(result), file=sys.stdout)
        sys.stdout.flush()
        
    except Exception as e:
        error_response = {
            "error": str(e),
            "answer": "Sorry, I encountered an error processing your message."
        }
        print(json.dumps(error_response))
        sys.exit(1)


if __name__ == "__main__":
    main()

