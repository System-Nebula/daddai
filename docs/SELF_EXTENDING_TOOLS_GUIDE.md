# Self-Extending Tools System Guide

## Overview

The enhanced RAG system now includes a **self-extending tool system** that allows the LLM to write, test, and register its own tools safely. All tool execution is **non-destructive** and validated.

## Key Features

### 1. **Non-Destructive Execution**
- All tool code runs in a sandbox
- Forbidden operations are blocked (file deletion, system calls, etc.)
- Code is validated before execution
- No permanent changes to system files

### 2. **Safe Tool Creation**
- LLM can write new tools
- Code is validated for safety
- Tools are stored but not executed until tested

### 3. **Tool Testing**
- Tools can be tested with test cases
- Tests run in sandbox
- Results are validated
- Only tested tools can be registered

### 4. **Tool Registration**
- Only tools that pass tests can be registered
- Registered tools become available immediately
- Tool usage is tracked

## Meta-Tools (Tools for Creating Tools)

### `write_tool`
Write a new tool/function.

**Parameters:**
- `code`: Python code defining the function
- `function_name`: Name of the function
- `description`: What the tool does
- `parameters`: JSON schema for parameters

**Example:**
```json
{
  "tool": "write_tool",
  "arguments": {
    "code": "def calculate_total(items):\n    return sum(item['price'] * item['quantity'] for item in items)",
    "function_name": "calculate_total",
    "description": "Calculate total price from a list of items",
    "parameters": {
      "type": "object",
      "properties": {
        "items": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "price": {"type": "number"},
              "quantity": {"type": "integer"}
            }
          }
        }
      },
      "required": ["items"]
    }
  }
}
```

### `test_tool`
Test a stored tool with test cases.

**Parameters:**
- `tool_name`: Name of tool to test
- `test_cases`: List of test cases with `arguments` and optionally `expected_result`

**Example:**
```json
{
  "tool": "test_tool",
  "arguments": {
    "tool_name": "calculate_total",
    "test_cases": [
      {
        "arguments": {
          "items": [{"price": 10, "quantity": 2}, {"price": 5, "quantity": 3}]
        },
        "expected_result": 35
      }
    ]
  }
}
```

### `register_tool`
Register a tested tool so it can be used.

**Parameters:**
- `tool_name`: Name of tool to register

**Example:**
```json
{
  "tool": "register_tool",
  "arguments": {
    "tool_name": "calculate_total"
  }
}
```

### `list_stored_tools`
List all stored tools.

**Example:**
```json
{
  "tool": "list_stored_tools",
  "arguments": {}
}
```

### `execute_stored_tool`
Execute a stored tool safely (for testing).

**Parameters:**
- `tool_name`: Name of tool
- `arguments`: Arguments to pass

### `get_tool_code`
Get the code for a stored tool.

**Parameters:**
- `tool_name`: Name of tool

## Workflow: Creating a New Tool

### Step 1: Write the Tool
```
LLM calls write_tool with code, function name, description, and parameters
→ Tool is validated and stored (not executed yet)
```

### Step 2: Test the Tool
```
LLM calls test_tool with test cases
→ Tool is executed safely in sandbox
→ Test results are stored
```

### Step 3: Register the Tool
```
LLM calls register_tool
→ Tool is registered and becomes available
→ Can now be called like any other tool
```

## Safety Features

### Code Validation
- **AST Parsing**: Code is parsed to check for dangerous operations
- **Forbidden Imports**: Blocks dangerous modules (os, sys, subprocess, etc.)
- **Forbidden Functions**: Blocks eval, exec, __import__, etc.
- **Pattern Detection**: Checks for dangerous patterns in code

### Sandbox Execution
- **Isolated Environment**: Tools run in isolated namespace
- **Limited Built-ins**: Only safe built-in functions available
- **Timeout Protection**: Execution times out after 5 seconds
- **Error Handling**: All errors are caught and reported safely

### Non-Destructive Guarantees
- **No File Operations**: Cannot read/write files
- **No System Calls**: Cannot execute system commands
- **No Network Access**: Cannot make network requests
- **No Persistent Changes**: Cannot modify system state

## Example: LLM Creating a Tool

**User:** "Create a tool that calculates the average of a list of numbers"

**LLM Process:**

1. **Writes Tool:**
```python
{
  "tool": "write_tool",
  "arguments": {
    "code": "def calculate_average(numbers):\n    if not numbers:\n        return 0\n    return sum(numbers) / len(numbers)",
    "function_name": "calculate_average",
    "description": "Calculate the average of a list of numbers",
    "parameters": {
      "type": "object",
      "properties": {
        "numbers": {
          "type": "array",
          "items": {"type": "number"}
        }
      },
      "required": ["numbers"]
    }
  }
}
```

2. **Tests Tool:**
```python
{
  "tool": "test_tool",
  "arguments": {
    "tool_name": "calculate_average",
    "test_cases": [
      {
        "arguments": {"numbers": [1, 2, 3, 4, 5]},
        "expected_result": 3.0
      },
      {
        "arguments": {"numbers": [10, 20, 30]},
        "expected_result": 20.0
      }
    ]
  }
}
```

3. **Registers Tool:**
```python
{
  "tool": "register_tool",
  "arguments": {
    "tool_name": "calculate_average"
  }
}
```

4. **Uses Tool:**
Now the LLM can call `calculate_average` like any other tool!

## Allowed Operations

Tools can safely use:
- Mathematical operations (+, -, *, /, etc.)
- String operations (formatting, splitting, etc.)
- List/dict operations (filtering, mapping, etc.)
- JSON operations
- Date/time operations
- Safe built-in functions

## Forbidden Operations

Tools **cannot** use:
- File I/O (open, read, write)
- System calls (os.system, subprocess)
- Network operations
- Importing dangerous modules
- eval/exec
- Deleting/modifying system state

## Tool Storage

- Tools are stored in `llm_tools_storage.json`
- Each tool includes: code, description, parameters, test results
- Tool usage is tracked
- Tools persist across sessions

## Best Practices

1. **Always Test**: Test tools before registering
2. **Write Tests**: Include multiple test cases
3. **Validate Inputs**: Tools should validate their inputs
4. **Handle Errors**: Tools should handle errors gracefully
5. **Keep It Simple**: Simple tools are easier to test and debug

## Debugging

To see tool execution history:
```python
sandbox = pipeline.tool_sandbox
print("Execution history:", sandbox.execution_history)
```

To see stored tools:
```python
storage = pipeline.tool_storage
print("Stored tools:", storage.list_tools())
```

## Example Use Cases

### Use Case 1: Custom Calculator
LLM creates tools for specific calculations needed by users.

### Use Case 2: Data Processing
LLM creates tools to process user data in specific ways.

### Use Case 3: Format Converters
LLM creates tools to convert between formats.

### Use Case 4: Custom Validators
LLM creates tools to validate user input in specific ways.

## Security Considerations

- All code is validated before execution
- Sandbox prevents destructive operations
- Timeout prevents infinite loops
- Error handling prevents crashes
- Tool storage is separate from system files

## Future Enhancements

Potential improvements:
- Tool versioning
- Tool dependencies
- Tool composition
- Tool sharing between instances
- Advanced testing frameworks

