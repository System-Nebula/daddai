# Tool Calling Integration

This document explains how tool calling works with the OpenAI-compatible client.

## Overview

The system supports two methods of tool calling:

1. **Native Function Calling** (OpenAI format) - Structured tool calls returned by the API
2. **Text-based Tool Calling** (Legacy) - Parsing tool calls from text responses

## Native Function Calling

When using providers that support OpenAI's function calling format (like Chutes AI), you can pass tools directly to the API:

### Basic Usage

```python
from src.clients.llm_client_factory import get_llm_client
from src.tools.llm_tools import LLMToolRegistry

# Get client
client = get_llm_client(provider="chutes")

# Get tool registry
registry = LLMToolRegistry()
# ... register tools ...

# Get tools in OpenAI format
tools_schema = registry.get_tools_schema()

# Make request with tools
messages = [
    {"role": "user", "content": "What's the weather in New York?"}
]

response = client.generate_response(
    messages=messages,
    tools=tools_schema,
    tool_choice="auto"  # or "none" or specific function
)

# Check if tools were called
if isinstance(response, dict) and 'tool_calls' in response:
    tool_calls = response['tool_calls']
    content = response.get('content', '')
    
    # Execute tools
    for tool_call in tool_calls:
        function_name = tool_call['function']['name']
        arguments = json.loads(tool_call['function']['arguments'])
        # ... execute tool ...
        
        # Add tool result to messages
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call['id'],
            "content": json.dumps(tool_result)
        })
    
    # Continue conversation with tool results
    final_response = client.generate_response(messages=messages, tools=tools_schema)
else:
    # Regular text response
    print(response)
```

### Tool Schema Format

Tools should be in OpenAI's function calling format:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather in a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"]
                    }
                },
                "required": ["location"]
            }
        }
    }
]
```

### Tool Choice Options

- `"auto"` - Let the model decide when to call tools (default)
- `"none"` - Don't call any tools
- `{"type": "function", "function": {"name": "tool_name"}}` - Force a specific tool

### Streaming with Tools

```python
for chunk in client.generate_stream(
    messages=messages,
    tools=tools_schema,
    tool_choice="auto"
):
    if chunk.get('content'):
        print(chunk['content'], end='', flush=True)
    
    # Tool calls may appear in chunks
    if chunk.get('tool_calls'):
        for tool_call in chunk['tool_calls']:
            # Handle tool call
            pass
```

## Integration with Existing Tool System

The existing `LLMToolRegistry` already provides `get_tools_schema()` which returns tools in the correct format:

```python
from src.tools.llm_tools import create_rag_tools, LLMToolExecutor

# Create tool registry
registry = create_rag_tools(pipeline)
executor = LLMToolExecutor(registry)

# Get tools in OpenAI format
tools_schema = registry.get_tools_schema()

# Use with client
response = client.generate_response(
    messages=messages,
    tools=tools_schema
)

# Execute tool calls if present
if isinstance(response, dict) and 'tool_calls' in response:
    tool_results = executor.execute_tool_calls(response['tool_calls'])
    
    # Format results and add to messages
    for i, tool_call in enumerate(response['tool_calls']):
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call['id'],
            "content": LLMToolParser.format_tool_result(
                tool_call['function']['name'],
                tool_results[i]['result']
            )
        })
    
    # Continue with tool results
    final_response = client.generate_response(messages=messages, tools=tools_schema)
```

## Text-based Tool Calling (Legacy)

The existing system still works for providers that don't support native function calling:

1. Tools are described in the system prompt
2. LLM generates text with tool calls in JSON format
3. `LLMToolParser.parse_tool_calls()` extracts tool calls from text
4. Tools are executed and results added back to conversation

This method is used when:
- Provider doesn't support function calling
- `tools` parameter is not provided
- Fallback for compatibility

## Example: Complete Tool Calling Flow

```python
from src.clients.llm_client_factory import get_llm_client
from src.tools.llm_tools import create_rag_tools, LLMToolExecutor, LLMToolParser

# Setup
client = get_llm_client(provider="chutes")
registry = create_rag_tools(pipeline)
executor = LLMToolExecutor(registry)
tools_schema = registry.get_tools_schema()

# Initial request
messages = [
    {"role": "user", "content": "Summarize this YouTube video: https://youtube.com/watch?v=abc123"}
]

# First call - model may decide to call tools
response = client.generate_response(
    messages=messages,
    tools=tools_schema,
    tool_choice="auto"
)

# Handle tool calls
if isinstance(response, dict) and 'tool_calls' in response:
    # Execute all tool calls
    tool_results = []
    for tool_call in response['tool_calls']:
        result = executor.execute_tool_call({
            "name": tool_call['function']['name'],
            "arguments": json.loads(tool_call['function']['arguments'])
        })
        tool_results.append(result)
        
        # Add tool result to messages
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call['id'],
            "content": LLMToolParser.format_tool_result(
                tool_call['function']['name'],
                result['result']
            )
        })
    
    # Get final response with tool results
    final_response = client.generate_response(
        messages=messages,
        tools=tools_schema
    )
    
    if isinstance(final_response, dict):
        print(final_response.get('content', ''))
    else:
        print(final_response)
else:
    # No tools called, direct response
    print(response)
```

## Benefits of Native Function Calling

1. **Structured Responses** - Tool calls are structured, not parsed from text
2. **More Reliable** - No regex parsing, fewer errors
3. **Better Performance** - API handles tool selection
4. **Streaming Support** - Tool calls can appear in streaming responses
5. **Provider Optimized** - Providers can optimize tool selection

## Compatibility

- ✅ **Chutes AI** - Supports native function calling
- ✅ **OpenAI** - Supports native function calling
- ✅ **LMStudio** - May support depending on model
- ⚠️ **Custom Providers** - Depends on provider implementation

For providers that don't support native function calling, the system automatically falls back to text-based tool calling.

