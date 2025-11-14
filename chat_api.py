"""
Simple chat API for Discord bot - direct LMStudio call without RAG.
Returns JSON responses for easy integration.
"""
import json
import sys
import argparse
from lmstudio_client import LMStudioClient

def main():
    parser = argparse.ArgumentParser(description='Simple Chat API for Discord bot')
    parser.add_argument('--message', type=str, required=True, help='Message to send')
    parser.add_argument('--history', type=str, default=None, help='JSON array of conversation history')
    
    args = parser.parse_args()
    
    try:
        # Initialize LMStudio client (model detection happens here, but only once per process)
        # For faster responses, we could cache this, but subprocess means new process each time
        client = LMStudioClient()
        
        # Parse conversation history if provided
        messages = []
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
                            messages.append(item)
            except json.JSONDecodeError:
                pass
        
        # Add current message
        messages.append({"role": "user", "content": args.message})
        
        # Generate response with optimized settings for speed
        response = client.generate_response(
            messages=messages,
            temperature=0.7,
            max_tokens=500  # Reduced from 1000 for faster responses
        )
        
        # Return JSON response
        result = {
            "answer": response,
            "message": args.message
        }
        
        # Only output JSON to stdout (no debug info)
        print(json.dumps(result), file=sys.stdout)
        sys.stdout.flush()  # Ensure output is sent immediately
        
    except Exception as e:
        error_response = {
            "error": str(e),
            "answer": "Sorry, I encountered an error processing your message."
        }
        print(json.dumps(error_response))
        sys.exit(1)


if __name__ == "__main__":
    main()

