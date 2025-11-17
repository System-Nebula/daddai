# Quick Test Guide for Tool Calling

## Setup

1. **Set your Chutes API key** in `.env` file:
```env
CHUTES_API_KEY=your-api-key-here
LLM_PROVIDER=chutes
CHUTES_MODEL=moonshotai/Kimi-K2-Thinking
```

2. **Run the test**:
```bash
python examples/test_tool_calling.py
```

## What the Test Does

The test script runs 4 tests:

1. **Basic Connection Test** - Verifies API connectivity
2. **Native Function Calling** - Tests tool calling with a simple weather tool
3. **Streaming with Tools** - Tests streaming responses with tool calls
4. **Multiple Tool Calls** - Tests calling multiple tools in one request

## Expected Output

When working correctly, you should see:

```
✅ Client initialized: https://llm.chutes.ai/v1
✅ Response received: Hello, tool calling test!

✅ Tool calls detected: 1
Tool Call 1:
  ID: call_abc123
  Function: get_weather
  Arguments: {"location": "New York", "unit": "celsius"}
  ✅ Tool executed successfully
  Result: {"location": "New York", "temperature": 22, ...}

✅ Final response: The weather in New York is 22°C and sunny...
```

## Manual Test

You can also test manually in Python:

```python
from src.clients.llm_client_factory import get_llm_client
from src.tools.llm_tools import LLMTool, LLMToolRegistry, LLMToolExecutor
import json

# Create a simple tool
registry = LLMToolRegistry()
executor = LLMToolExecutor(registry)

def get_weather(location: str):
    return {"location": location, "temp": 22, "condition": "sunny"}

registry.register_tool(LLMTool(
    name="get_weather",
    description="Get weather for a location",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City name"}
        },
        "required": ["location"]
    },
    function=get_weather
))

# Get client and tools
client = get_llm_client(provider="chutes")
tools = registry.get_tools_schema()

# Make request
response = client.generate_response(
    messages=[{"role": "user", "content": "What's the weather in Paris?"}],
    tools=tools,
    tool_choice="auto"
)

# Handle tool calls
if isinstance(response, dict) and 'tool_calls' in response:
    for tool_call in response['tool_calls']:
        args = json.loads(tool_call['function']['arguments'])
        result = executor.execute_tool_call({
            "name": tool_call['function']['name'],
            "arguments": args
        })
        print(f"Tool result: {result}")
```

## Troubleshooting

- **API Key Error**: Make sure `CHUTES_API_KEY` is set in `.env`
- **No Tool Calls**: Some models may not call tools if they think they can answer directly
- **Connection Error**: Check your internet connection and API endpoint
- **Encoding Errors**: The script handles Windows encoding automatically

