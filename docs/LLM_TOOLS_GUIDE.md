# LLM Tools System Guide

## Overview

The enhanced RAG system now includes a robust tool calling system that allows the LLM to dynamically call functions during generation. This enables the LLM to:
- Query user state
- Search documents when needed
- Transfer items/resources
- Access memories
- Get user profiles and relationships

## How It Works

### 1. Tool Registration

Tools are automatically registered when the pipeline is initialized. Each tool includes:
- **Name**: Function identifier
- **Description**: What the tool does (for LLM understanding)
- **Parameters**: JSON schema defining inputs
- **Function**: Python function to execute

### 2. Tool Calling Process

1. **LLM receives query** with available tools listed
2. **LLM decides** if it needs to call a tool
3. **LLM formats tool call** (JSON or function call format)
4. **System executes tool** and returns result
5. **LLM uses result** to generate final answer

### 3. Multi-Turn Tool Calling

The system supports multiple tool call iterations:
- LLM can call tools
- Use results
- Call more tools if needed
- Up to 3 iterations by default

## Available Tools

### State Management Tools

#### `get_user_state`
Get a user's state (gold, inventory, level, etc.)

**Example:**
```json
{"tool": "get_user_state", "arguments": {"user_id": "123456789", "key": "gold"}}
```

**Returns:**
```json
{"user_id": "123456789", "key": "gold", "value": 100}
```

#### `transfer_state`
Transfer state value (gold, coins) between users

**Example:**
```json
{"tool": "transfer_state", "arguments": {
    "from_user_id": "123456789",
    "to_user_id": "987654321",
    "key": "gold",
    "amount": 20
}}
```

#### `transfer_item`
Transfer an item between user inventories

**Example:**
```json
{"tool": "transfer_item", "arguments": {
    "from_user_id": "123456789",
    "to_user_id": "987654321",
    "item": "sword",
    "quantity": 1
}}
```

#### `set_user_state`
Set a user's state value

**Example:**
```json
{"tool": "set_user_state", "arguments": {
    "user_id": "123456789",
    "key": "level",
    "value": 10
}}
```

### Document Tools

#### `search_documents`
Search documents for information

**Example:**
```json
{"tool": "search_documents", "arguments": {
    "query": "project status",
    "max_results": 5
}}
```

**Returns:**
```json
[
    {
        "text": "The project is on track...",
        "file_name": "project_report.pdf",
        "score": 0.95
    }
]
```

#### `list_documents`
List all available documents

**Example:**
```json
{"tool": "list_documents", "arguments": {"limit": 20}}
```

### User Tools

#### `get_user_profile`
Get a user's profile and statistics

**Example:**
```json
{"tool": "get_user_profile", "arguments": {"user_id": "123456789"}}
```

#### `get_user_relationships`
Get a user's relationships with other users

**Example:**
```json
{"tool": "get_user_relationships", "arguments": {
    "user_id": "123456789",
    "top_n": 10
}}
```

### Memory Tools

#### `get_memories`
Get relevant memories from a channel

**Example:**
```json
{"tool": "get_memories", "arguments": {
    "channel_id": "111222333",
    "query": "previous conversation about gold",
    "top_k": 5
}}
```

## Tool Call Formats

The LLM can use tools in multiple formats:

### JSON Format
```json
{"tool": "get_user_state", "arguments": {"user_id": "123456789", "key": "gold"}}
```

### Function Call Format
```
get_user_state(user_id="123456789", key="gold")
```

### XML-Like Format
```xml
<tool_call>get_user_state</tool_call>
<arguments>{"user_id": "123456789", "key": "gold"}</arguments>
```

## Example Interactions

### Example 1: State Query

**User:** "How much gold does @alexei have?"

**LLM Process:**
1. LLM calls `get_user_state(user_id="alexei_id", key="gold")`
2. Tool returns: `{"value": 20}`
3. LLM responds: "@alexei has 20 gold pieces."

### Example 2: Document Search

**User:** "What does the project plan say about deadlines?"

**LLM Process:**
1. LLM calls `search_documents(query="deadlines project plan", max_results=3)`
2. Tool returns relevant document chunks
3. LLM uses chunks to answer: "According to the project plan, deadlines are..."

### Example 3: Multi-Tool Query

**User:** "Give @alexei 20 gold and tell me how much he has now"

**LLM Process:**
1. LLM calls `transfer_state(from_user_id="user_id", to_user_id="alexei_id", key="gold", amount=20)`
2. Tool returns: `{"to_value": 40}` (was 20, now 40)
3. LLM responds: "Gave 20 gold to @alexei. They now have 40 gold pieces."

### Example 4: Complex Query

**User:** "What documents mention @alexei and what's his current gold balance?"

**LLM Process:**
1. LLM calls `get_user_state(user_id="alexei_id", key="gold")` → Returns gold balance
2. LLM calls `search_documents(query="alexei", max_results=5)` → Returns documents mentioning Alexei
3. LLM combines results: "@alexei has 40 gold. He's mentioned in documents: project_plan.pdf, team_roster.pdf..."

## Benefits

1. **Dynamic Tool Selection**: LLM decides when to use tools
2. **Flexible Queries**: Can handle complex multi-part questions
3. **Accurate State**: Always uses current state values
4. **Efficient**: Only searches documents when needed
5. **Extensible**: Easy to add new tools

## Adding Custom Tools

To add a custom tool:

```python
from llm_tools import LLMTool, LLMToolRegistry

def my_custom_tool(param1: str, param2: int) -> Dict[str, Any]:
    """Do something custom."""
    return {"result": f"Processed {param1} with {param2}"}

# Register tool
tool = LLMTool(
    name="my_custom_tool",
    description="Does something custom",
    parameters={
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
            "param2": {"type": "integer"}
        },
        "required": ["param1", "param2"]
    },
    function=my_custom_tool
)

registry.register_tool(tool)
```

## Configuration

Tool calling behavior can be configured:

- **max_iterations**: Maximum tool call iterations (default: 3)
- **tool_timeout**: Timeout for tool execution (default: 5 seconds)
- **enable_tools**: Enable/disable tool calling (default: True)

## Best Practices

1. **Tool Descriptions**: Write clear, specific descriptions so LLM knows when to use tools
2. **Parameter Validation**: Tools should validate inputs
3. **Error Handling**: Tools should return error information, not raise exceptions
4. **Result Formatting**: Format tool results clearly for LLM consumption
5. **Tool Limits**: Don't register too many tools (10-15 is optimal)

## Debugging

To see tool calls in action:

```python
result = pipeline.query("how much gold does @alexei have?")
print("Tool calls used:", result.get("tool_calls", []))
```

Tool execution history is also available:
```python
executor = pipeline.tool_executor
print("Execution history:", executor.execution_history)
```

