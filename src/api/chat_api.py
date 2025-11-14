"""
Simple chat API for Discord bot - direct LMStudio call without RAG.
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

from src.clients.lmstudio_client import LMStudioClient

def main():
    parser = argparse.ArgumentParser(description='Simple Chat API for Discord bot')
    parser.add_argument('--message', type=str, required=True, help='Message to send')
    parser.add_argument('--history', type=str, default=None, help='JSON array of conversation history')
    
    args = parser.parse_args()
    
    try:
        # Initialize LMStudio client (model detection happens here, but only once per process)
        # For faster responses, we could cache this, but subprocess means new process each time
        client = LMStudioClient()
        
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
        
        # Generate response with optimized settings for speed and personality
        response = client.generate_response(
            messages=messages,
            temperature=0.85,  # Higher temperature for more creative, bubbly responses
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

