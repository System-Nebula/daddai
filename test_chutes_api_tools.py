"""Test Chutes API with tool calling to diagnose hanging issues."""
import os
import sys
import time
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.clients.llm_client_factory import get_default_llm_client
from config import LLM_PROVIDER, CHUTES_API_KEY, CHUTES_BASE_URL, CHUTES_MODEL

print("=" * 70)
print("Chutes API Tool Calling Test")
print("=" * 70)
print(f"Provider: {LLM_PROVIDER}")
print(f"Base URL: {CHUTES_BASE_URL}")
print(f"Model: {CHUTES_MODEL}")
print(f"API Key: {'Set' if CHUTES_API_KEY else 'NOT SET'}")
print()

# Test 1: Basic connection without tools
print("Test 1: Basic API call (no tools)")
print("-" * 70)
try:
    client = get_default_llm_client()
    print(f"✅ Client initialized: {type(client).__name__}")
    
    start_time = time.time()
    response = client.generate_response(
        messages=[
            {"role": "user", "content": "Say 'Hello, this is a test'"}
        ],
        temperature=0.7,
        max_tokens=50
    )
    elapsed = time.time() - start_time
    print(f"✅ Response received in {elapsed:.2f}s")
    print(f"   Response: {response[:100]}...")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("Test 2: API call with tools (this is where hanging might occur)")
print("-" * 70)

# Create a simple tool definition
test_tools = [
    {
        "type": "function",
        "function": {
            "name": "summarize_website",
            "description": "Fetch and summarize a website URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The website URL to summarize"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

try:
    print(f"📤 Sending request with {len(test_tools)} tool(s)...")
    print(f"   Tool: {test_tools[0]['function']['name']}")
    
    start_time = time.time()
    
    # Test with a URL in the message (like the Discord bot does)
    response = client.generate_response(
        messages=[
            {"role": "user", "content": "Summarize this URL: https://example.com"}
        ],
        temperature=0.7,
        max_tokens=100,
        tools=test_tools,
        tool_choice="auto"
    )
    
    elapsed = time.time() - start_time
    print(f"✅ Response received in {elapsed:.2f}s")
    
    if isinstance(response, dict):
        print(f"   Response type: dict")
        print(f"   Keys: {list(response.keys())}")
        if 'tool_calls' in response:
            print(f"   Tool calls: {len(response.get('tool_calls', []))}")
            for tc in response.get('tool_calls', []):
                print(f"      - {tc.get('function', {}).get('name', 'unknown')}")
        if 'content' in response:
            print(f"   Content: {response.get('content', '')[:100]}...")
    else:
        print(f"   Response type: {type(response).__name__}")
        print(f"   Response: {str(response)[:200]}...")
        
except Exception as e:
    elapsed = time.time() - start_time if 'start_time' in locals() else 0
    print(f"❌ Error after {elapsed:.2f}s: {e}")
    print(f"   Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()

print()
print("Test 3: Direct HTTP request to Chutes API (bypassing client)")
print("-" * 70)

try:
    import requests
    
    payload = {
        "model": CHUTES_MODEL,
        "messages": [
            {"role": "user", "content": "Say 'test'"}
        ],
        "temperature": 0.7,
        "max_tokens": 10
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    if CHUTES_API_KEY:
        headers["Authorization"] = f"Bearer {CHUTES_API_KEY}"
    
    print(f"📤 Sending direct HTTP request to {CHUTES_BASE_URL}/chat/completions")
    print(f"   Timeout: 30s")
    
    start_time = time.time()
    response = requests.post(
        f"{CHUTES_BASE_URL}/chat/completions",
        json=payload,
        headers=headers,
        timeout=30
    )
    elapsed = time.time() - start_time
    
    print(f"✅ Response received in {elapsed:.2f}s")
    print(f"   Status code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        if 'choices' in result:
            content = result['choices'][0].get('message', {}).get('content', '')
            print(f"   Content: {content}")
        else:
            print(f"   Response: {json.dumps(result, indent=2)[:500]}")
    else:
        print(f"   Error: {response.text[:500]}")
        
except Exception as e:
    elapsed = time.time() - start_time if 'start_time' in locals() else 0
    print(f"❌ Error after {elapsed:.2f}s: {e}")
    import traceback
    traceback.print_exc()

print()
print("Test 4: Direct HTTP request with tools")
print("-" * 70)

try:
    payload = {
        "model": CHUTES_MODEL,
        "messages": [
            {"role": "user", "content": "Summarize https://example.com"}
        ],
        "temperature": 0.7,
        "max_tokens": 100,
        "tools": test_tools,
        "tool_choice": "auto"
    }
    
    print(f"📤 Sending HTTP request with tools...")
    print(f"   Payload size: {len(json.dumps(payload))} bytes")
    
    start_time = time.time()
    response = requests.post(
        f"{CHUTES_BASE_URL}/chat/completions",
        json=payload,
        headers=headers,
        timeout=30
    )
    elapsed = time.time() - start_time
    
    print(f"✅ Response received in {elapsed:.2f}s")
    print(f"   Status code: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        if 'choices' in result:
            message = result['choices'][0].get('message', {})
            if 'tool_calls' in message:
                print(f"   ✅ Tool calls received: {len(message['tool_calls'])}")
                for tc in message['tool_calls']:
                    func = tc.get('function', {})
                    print(f"      - {func.get('name')}: {func.get('arguments', {})}")
            else:
                content = message.get('content', '')
                print(f"   Content (no tool calls): {content[:200]}")
        else:
            print(f"   Response: {json.dumps(result, indent=2)[:500]}")
    else:
        print(f"   Error: {response.text[:500]}")
        
except requests.exceptions.Timeout:
    elapsed = time.time() - start_time if 'start_time' in locals() else 0
    print(f"⏱️  TIMEOUT after {elapsed:.2f}s - This is likely the hanging issue!")
    print(f"   The API call exceeded 30 seconds and timed out.")
except Exception as e:
    elapsed = time.time() - start_time if 'start_time' in locals() else 0
    print(f"❌ Error after {elapsed:.2f}s: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("Test Complete")
print("=" * 70)

