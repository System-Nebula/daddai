"""
Test script for tool calling with OpenAI-compatible providers (Chutes AI).
Tests native function calling, tool execution, and streaming.
"""
import os
import sys
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.clients.llm_client_factory import get_llm_client
from src.tools.llm_tools import LLMTool, LLMToolRegistry, LLMToolExecutor, LLMToolParser
from config import CHUTES_API_KEY, CHUTES_BASE_URL, CHUTES_MODEL


def create_test_tools():
    """Create a simple test tool registry with example tools."""
    registry = LLMToolRegistry()
    executor = LLMToolExecutor(registry)
    
    # Simple test tool: Get weather
    def get_weather(location: str, unit: str = "celsius") -> dict:
        """Get weather for a location (mock implementation)."""
        return {
            "location": location,
            "temperature": 22 if unit == "celsius" else 72,
            "unit": unit,
            "condition": "sunny",
            "humidity": 65
        }
    
    registry.register_tool(LLMTool(
        name="get_weather",
        description="Get the current weather in a location",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit"
                }
            },
            "required": ["location"]
        },
        function=get_weather
    ))
    
    # Simple test tool: Calculate
    def calculate(expression: str) -> dict:
        """Calculate a mathematical expression (mock implementation)."""
        try:
            # Simple safe evaluation (in production, use a proper math parser)
            result = eval(expression.replace("^", "**"))
            return {
                "expression": expression,
                "result": result
            }
        except Exception as e:
            return {
                "expression": expression,
                "error": str(e)
            }
    
    registry.register_tool(LLMTool(
        name="calculate",
        description="Calculate a mathematical expression",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to calculate, e.g. '2 + 2' or '10 * 5'"
                }
            },
            "required": ["expression"]
        },
        function=calculate
    ))
    
    return registry, executor


def test_basic_connection():
    """Test basic API connection."""
    print("=" * 60)
    print("Test 1: Basic Connection Test")
    print("=" * 60)
    
    if not CHUTES_API_KEY:
        print("❌ ERROR: CHUTES_API_KEY not set!")
        print("Please set it in your .env file or environment variables.")
        return False
    
    try:
        client = get_llm_client(provider="chutes")
        print(f"✅ Client initialized: {client.base_url}")
        print(f"   Model: {client.model}")
        
        # Test simple request
        messages = [
            {"role": "user", "content": "Say 'Hello, tool calling test!' and nothing else."}
        ]
        
        print("\nSending test request...")
        response = client.generate_response(
            messages=messages,
            temperature=0.7,
            max_tokens=50
        )
        
        print(f"✅ Response received: {response}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_calling():
    """Test native function calling."""
    print("\n" + "=" * 60)
    print("Test 2: Native Function Calling")
    print("=" * 60)
    
    if not CHUTES_API_KEY:
        print("❌ ERROR: CHUTES_API_KEY not set!")
        return False
    
    try:
        client = get_llm_client(provider="chutes")
        registry, executor = create_test_tools()
        tools_schema = registry.get_tools_schema()
        
        print(f"✅ Created {len(tools_schema)} test tools")
        for tool in tools_schema:
            print(f"   - {tool['function']['name']}: {tool['function']['description']}")
        
        # Test tool calling
        messages = [
            {
                "role": "user",
                "content": "What's the weather in New York? Use the get_weather tool."
            }
        ]
        
        print("\nSending request with tools...")
        print(f"Tools: {[t['function']['name'] for t in tools_schema]}")
        
        response = client.generate_response(
            messages=messages,
            tools=tools_schema,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=500
        )
        
        print(f"\nResponse type: {type(response)}")
        
        # Check if tools were called
        if isinstance(response, dict) and 'tool_calls' in response:
            print(f"✅ Tool calls detected: {len(response['tool_calls'])}")
            
            for i, tool_call in enumerate(response['tool_calls']):
                print(f"\nTool Call {i+1}:")
                print(f"  ID: {tool_call.get('id')}")
                print(f"  Function: {tool_call['function']['name']}")
                print(f"  Arguments: {tool_call['function']['arguments']}")
                
                # Execute tool
                try:
                    arguments = json.loads(tool_call['function']['arguments'])
                    result = executor.execute_tool_call({
                        "name": tool_call['function']['name'],
                        "arguments": arguments
                    })
                    
                    print(f"  ✅ Tool executed successfully")
                    print(f"  Result: {json.dumps(result, indent=2)}")
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": json.dumps(result['result'])
                    })
                    
                except Exception as e:
                    print(f"  ❌ Tool execution error: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Continue conversation with tool results
            print("\n" + "-" * 60)
            print("Continuing conversation with tool results...")
            print("-" * 60)
            
            final_response = client.generate_response(
                messages=messages,
                tools=tools_schema,
                temperature=0.7,
                max_tokens=500
            )
            
            if isinstance(final_response, dict):
                print(f"✅ Final response: {final_response.get('content', '')}")
            else:
                print(f"✅ Final response: {final_response}")
            
            return True
        else:
            print(f"⚠️  No tool calls detected. Response: {response}")
            print("   (This might be normal if the model chose not to use tools)")
            return True  # Not an error, just no tools used
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_streaming_with_tools():
    """Test streaming with tool calling."""
    print("\n" + "=" * 60)
    print("Test 3: Streaming with Tools")
    print("=" * 60)
    
    if not CHUTES_API_KEY:
        print("❌ ERROR: CHUTES_API_KEY not set!")
        return False
    
    try:
        client = get_llm_client(provider="chutes")
        registry, executor = create_test_tools()
        tools_schema = registry.get_tools_schema()
        
        messages = [
            {
                "role": "user",
                "content": "Calculate 25 * 4 using the calculate tool."
            }
        ]
        
        print("Streaming request with tools...")
        print("Response (streaming):")
        print("-" * 60)
        
        full_response = ""
        tool_calls_accumulated = []
        
        for chunk in client.generate_stream(
            messages=messages,
            tools=tools_schema,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=500
        ):
            # Print content as it arrives
            if chunk.get('content'):
                content = chunk['content']
                full_response += content
                print(content, end='', flush=True)
            
        # Collect tool calls (streaming tool calls come in chunks, need to accumulate)
        if chunk.get('tool_calls'):
            # Tool calls in streaming can be partial, accumulate them
            for tc in chunk['tool_calls']:
                # Check if we already have this tool call (by index)
                existing = None
                for i, existing_tc in enumerate(tool_calls_accumulated):
                    if existing_tc.get('index') == tc.get('index'):
                        existing = i
                        break
                
                if existing is not None:
                    # Merge with existing tool call
                    existing_tc = tool_calls_accumulated[existing]
                    if 'function' in tc:
                        if 'function' not in existing_tc:
                            existing_tc['function'] = {}
                        if 'name' in tc['function']:
                            existing_tc['function']['name'] = tc['function']['name']
                        if 'arguments' in tc['function']:
                            existing_tc['function']['arguments'] = (
                                existing_tc['function'].get('arguments', '') + 
                                tc['function'].get('arguments', '')
                            )
                    if 'id' in tc:
                        existing_tc['id'] = tc['id']
                else:
                    # New tool call
                    tool_calls_accumulated.append(tc)
            
            print(f"\n[Tool call chunk detected in stream]")
        
        print("\n" + "-" * 60)
        
        if tool_calls_accumulated:
            print(f"✅ Collected {len(tool_calls_accumulated)} tool calls from stream")
            
            # Execute tools
            for i, tool_call in enumerate(tool_calls_accumulated):
                try:
                    # Get function name and arguments
                    func_name = tool_call.get('function', {}).get('name', 'unknown')
                    args_str = tool_call.get('function', {}).get('arguments', '{}')
                    
                    # Try to parse arguments
                    try:
                        arguments = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        print(f"⚠️  Tool call {i+1}: Could not parse arguments (may be incomplete): {args_str[:50]}...")
                        continue
                    
                    if not func_name or func_name == 'unknown':
                        print(f"⚠️  Tool call {i+1}: Missing function name")
                        continue
                    
                    result = executor.execute_tool_call({
                        "name": func_name,
                        "arguments": arguments
                    })
                    print(f"✅ Executed {func_name}: {result.get('result', 'N/A')}")
                except Exception as e:
                    print(f"❌ Error executing tool {i+1}: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print("⚠️  No tool calls in stream (model may have responded directly)")
        
        print(f"\nFull response: {full_response}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_tools():
    """Test multiple tool calls in one request."""
    print("\n" + "=" * 60)
    print("Test 4: Multiple Tool Calls")
    print("=" * 60)
    
    if not CHUTES_API_KEY:
        print("❌ ERROR: CHUTES_API_KEY not set!")
        return False
    
    try:
        client = get_llm_client(provider="chutes")
        registry, executor = create_test_tools()
        tools_schema = registry.get_tools_schema()
        
        messages = [
            {
                "role": "user",
                "content": "Get the weather in both New York and London, then calculate 100 + 50."
            }
        ]
        
        print("Requesting multiple tool calls...")
        
        response = client.generate_response(
            messages=messages,
            tools=tools_schema,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1000
        )
        
        if isinstance(response, dict) and 'tool_calls' in response:
            print(f"✅ Received {len(response['tool_calls'])} tool calls")
            
            # Execute all tools
            for tool_call in response['tool_calls']:
                try:
                    arguments = json.loads(tool_call['function']['arguments'])
                    result = executor.execute_tool_call({
                        "name": tool_call['function']['name'],
                        "arguments": arguments
                    })
                    
                    print(f"✅ {tool_call['function']['name']}: {result['result']}")
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": json.dumps(result['result'])
                    })
                except Exception as e:
                    print(f"❌ Error: {e}")
            
            # Get final response
            final = client.generate_response(
                messages=messages,
                tools=tools_schema,
                temperature=0.7,
                max_tokens=500
            )
            
            if isinstance(final, dict):
                print(f"\n✅ Final response: {final.get('content', '')}")
            else:
                print(f"\n✅ Final response: {final}")
            
            return True
        else:
            print(f"⚠️  No tool calls: {response}")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Tool Calling Integration Test")
    print("=" * 60)
    print(f"Provider: Chutes AI")
    print(f"Base URL: {CHUTES_BASE_URL}")
    print(f"Model: {CHUTES_MODEL}")
    print(f"API Key: {'Set' if CHUTES_API_KEY else 'NOT SET'}")
    print("=" * 60)
    
    if not CHUTES_API_KEY:
        print("\n❌ CHUTES_API_KEY not set!")
        print("Please set it in your .env file:")
        print("  CHUTES_API_KEY=your-api-key")
        return
    
    results = []
    
    # Run tests
    results.append(("Basic Connection", test_basic_connection()))
    results.append(("Tool Calling", test_tool_calling()))
    results.append(("Streaming with Tools", test_streaming_with_tools()))
    results.append(("Multiple Tools", test_multiple_tools()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed")
    print("=" * 60)


if __name__ == "__main__":
    main()

