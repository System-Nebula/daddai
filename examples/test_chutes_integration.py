"""
Example script demonstrating Chutes AI integration with streaming support.
This shows how to use the OpenAI-compatible client with Chutes API.
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.clients.llm_client_factory import get_llm_client
from config import CHUTES_API_KEY, CHUTES_BASE_URL, CHUTES_MODEL


def test_chutes_streaming():
    """Test Chutes AI with streaming support."""
    print("Testing Chutes AI integration with streaming...")
    print(f"Base URL: {CHUTES_BASE_URL}")
    print(f"Model: {CHUTES_MODEL}")
    print(f"API Key: {'Set' if CHUTES_API_KEY else 'Not set'}\n")
    
    if not CHUTES_API_KEY:
        print("ERROR: CHUTES_API_KEY not set in environment variables!")
        print("Please set it in your .env file or environment:")
        print("  export CHUTES_API_KEY='your-api-key'")
        return
    
    try:
        # Get Chutes client
        client = get_llm_client(provider="chutes")
        
        # Test messages
        messages = [
            {
                "role": "user",
                "content": "Tell me a 250 word story about a robot learning to paint."
            }
        ]
        
        print("Starting streaming request...\n")
        print("Response (streaming):")
        print("-" * 50)
        
        full_response = ""
        thinking_content = ""
        
        # Stream the response (with additional parameters example)
        for chunk in client.generate_stream(
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            top_p=0.9,  # Example: additional parameter
            presence_penalty=0.1  # Example: additional parameter
        ):
            # Print content chunks as they arrive
            if chunk.get('content'):
                content = chunk['content']
                full_response += content
                print(content, end='', flush=True)
            
            # Collect thinking content (for thinking models)
            if chunk.get('thinking'):
                thinking_content += chunk['thinking']
            
            # Check if finished
            if chunk.get('finish_reason'):
                print(f"\n\nFinished: {chunk['finish_reason']}")
        
        print("\n" + "-" * 50)
        print(f"\nTotal response length: {len(full_response)} characters")
        
        if thinking_content:
            print(f"Thinking content length: {len(thinking_content)} characters")
            print("\nThinking process (first 500 chars):")
            print(thinking_content[:500] + "..." if len(thinking_content) > 500 else thinking_content)
        
        print("\n✅ Streaming test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def test_chutes_non_streaming():
    """Test Chutes AI without streaming."""
    print("Testing Chutes AI integration (non-streaming)...")
    
    if not CHUTES_API_KEY:
        print("ERROR: CHUTES_API_KEY not set!")
        return
    
    try:
        client = get_llm_client(provider="chutes")
        
        messages = [
            {
                "role": "user",
                "content": "Write a haiku about artificial intelligence."
            }
        ]
        
        print("Sending request...")
        response = client.generate_response(
            messages=messages,
            temperature=0.7,
            max_tokens=200
        )
        
        print("\nResponse:")
        print("-" * 50)
        print(response)
        print("-" * 50)
        print("\n✅ Non-streaming test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Chutes AI integration')
    parser.add_argument('--mode', choices=['stream', 'non-stream', 'both'], 
                       default='both', help='Test mode')
    
    args = parser.parse_args()
    
    if args.mode in ['stream', 'both']:
        test_chutes_streaming()
        print("\n" + "=" * 60 + "\n")
    
    if args.mode in ['non-stream', 'both']:
        test_chutes_non_streaming()

