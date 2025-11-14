"""
Meta Tools - Tools that allow the LLM to create and test its own tools.
These are the foundational tools for self-extension.
"""
from typing import Dict, Any, List, Optional
from tool_sandbox import ToolSandbox, ToolStorage
from src.tools.llm_tools import LLMTool, LLMToolRegistry
from logger_config import logger


def create_meta_tools(sandbox: ToolSandbox, storage: ToolStorage, registry: LLMToolRegistry) -> List[LLMTool]:
    """
    Create meta-tools that allow LLM to create and test its own tools.
    
    Args:
        sandbox: Tool sandbox for safe execution
        storage: Tool storage for persistence
        registry: Tool registry to add new tools to
        
    Returns:
        List of meta-tools
    """
    tools = []
    
    # Tool: Write a new tool
    def write_tool(code: str, function_name: str, description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write a new tool. The code should define a function with the given name.
        This tool is non-destructive - it only validates and stores the tool.
        """
        # Validate code
        validation = sandbox.validate_code(code)
        if not validation["valid"]:
            return {
                "success": False,
                "error": f"Code validation failed: {', '.join(validation['errors'])}",
                "validation_errors": validation["errors"]
            }
        
        # Check if function exists in code
        try:
            # Quick check - try to compile
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            return {
                "success": False,
                "error": f"Syntax error: {str(e)}"
            }
        
        # Store tool (but don't register yet - needs testing first)
        stored = storage.store_tool(
            tool_name=function_name,
            code=code,
            description=description,
            parameters=parameters
        )
        
        if not stored:
            return {
                "success": False,
                "error": f"Tool '{function_name}' already exists"
            }
        
        return {
            "success": True,
            "message": f"Tool '{function_name}' written and stored. Use test_tool to test it before registering.",
            "tool_name": function_name
        }
    
    tools.append(LLMTool(
        name="write_tool",
        description="Write a new tool/function. Provide Python code that defines a function. This is non-destructive - it only validates and stores the tool. Use test_tool to test it before using.",
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code defining the function. Must be safe and non-destructive."
                },
                "function_name": {
                    "type": "string",
                    "description": "Name of the function to create"
                },
                "description": {
                    "type": "string",
                    "description": "Description of what the tool does"
                },
                "parameters": {
                    "type": "object",
                    "description": "JSON schema for function parameters",
                    "properties": {
                        "type": {"type": "string"},
                        "properties": {"type": "object"},
                        "required": {"type": "array"}
                    }
                }
            },
            "required": ["code", "function_name", "description", "parameters"]
        },
        function=write_tool
    ))
    
    # Tool: Test a tool
    def test_tool(tool_name: str, test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Test a stored tool with test cases.
        This safely executes the tool in a sandbox.
        """
        # Get tool from storage
        tool_data = storage.get_tool(tool_name)
        if not tool_data:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found. Use write_tool to create it first."
            }
        
        code = tool_data["code"]
        
        # Run tests
        test_results = sandbox.test_tool(
            code=code,
            function_name=tool_name,
            test_cases=test_cases
        )
        
        # Update storage with test results
        tool_data["test_results"] = test_results
        storage._save_tools()
        
        return {
            "success": True,
            "tool_name": tool_name,
            "test_results": test_results
        }
    
    tools.append(LLMTool(
        name="test_tool",
        description="Test a stored tool with test cases. Safely executes the tool in a sandbox. Use this to verify a tool works correctly before registering it.",
        parameters={
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool to test"
                },
                "test_cases": {
                    "type": "array",
                    "description": "List of test cases. Each test case should have 'arguments' (dict) and optionally 'expected_result'.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "arguments": {"type": "object"},
                            "expected_result": {}
                        },
                        "required": ["arguments"]
                    }
                }
            },
            "required": ["tool_name", "test_cases"]
        },
        function=test_tool
    ))
    
    # Tool: Register a tested tool
    def register_tool(tool_name: str) -> Dict[str, Any]:
        """
        Register a tested tool so it can be used.
        Only registers tools that have passed tests.
        """
        # Get tool from storage
        tool_data = storage.get_tool(tool_name)
        if not tool_data:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found"
            }
        
        # Check if tool has been tested
        test_results = tool_data.get("test_results")
        if not test_results:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' has not been tested. Use test_tool first."
            }
        
        # Check if tests passed
        if test_results.get("failed", 0) > 0:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' has failing tests. Fix the tool before registering.",
                "test_results": test_results
            }
        
        # Create executable function from stored code
        try:
            # Execute code to get function
            exec_globals = {}
            exec(tool_data["code"], exec_globals)
            
            if tool_name not in exec_globals:
                return {
                    "success": False,
                    "error": f"Function '{tool_name}' not found in code"
                }
            
            func = exec_globals[tool_name]
            
            # Create LLM tool
            llm_tool = LLMTool(
                name=tool_name,
                description=tool_data["description"],
                parameters=tool_data["parameters"],
                function=func
            )
            
            # Register tool
            registry.register_tool(llm_tool)
            
            return {
                "success": True,
                "message": f"Tool '{tool_name}' registered successfully and is now available for use.",
                "tool_name": tool_name
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Error registering tool: {str(e)}"
            }
    
    tools.append(LLMTool(
        name="register_tool",
        description="Register a tested tool so it can be used. Only registers tools that have passed all tests. Use this after test_tool confirms the tool works.",
        parameters={
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool to register"
                }
            },
            "required": ["tool_name"]
        },
        function=register_tool
    ))
    
    # Tool: List stored tools
    def list_stored_tools() -> Dict[str, Any]:
        """List all stored tools (tested and untested)."""
        tool_names = storage.list_tools()
        tools_info = []
        
        for name in tool_names:
            tool_data = storage.get_tool(name)
            tools_info.append({
                "name": name,
                "description": tool_data.get("description"),
                "tested": tool_data.get("test_results") is not None,
                "tests_passed": tool_data.get("test_results", {}).get("failed", 0) == 0 if tool_data.get("test_results") else None,
                "usage_count": tool_data.get("usage_count", 0)
            })
        
        return {
            "tools": tools_info,
            "total": len(tool_names)
        }
    
    tools.append(LLMTool(
        name="list_stored_tools",
        description="List all stored tools (both tested and untested). Use this to see what tools are available.",
        parameters={
            "type": "object",
            "properties": {}
        },
        function=list_stored_tools
    ))
    
    # Tool: Execute a stored tool (for testing)
    def execute_stored_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a stored tool safely.
        This is for testing purposes - registered tools are called automatically.
        """
        tool_data = storage.get_tool(tool_name)
        if not tool_data:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found"
            }
        
        # Execute in sandbox
        result = sandbox.execute_safely(
            code=tool_data["code"],
            function_name=tool_name,
            arguments=arguments
        )
        
        return result
    
    tools.append(LLMTool(
        name="execute_stored_tool",
        description="Execute a stored tool safely in sandbox. Use this to test a tool manually or verify it works.",
        parameters={
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool to execute"
                },
                "arguments": {
                    "type": "object",
                    "description": "Arguments to pass to the tool"
                }
            },
            "required": ["tool_name", "arguments"]
        },
        function=execute_stored_tool
    ))
    
    # Tool: Get tool code
    def get_tool_code(tool_name: str) -> Dict[str, Any]:
        """Get the code for a stored tool."""
        tool_data = storage.get_tool(tool_name)
        if not tool_data:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found"
            }
        
        return {
            "success": True,
            "tool_name": tool_name,
            "code": tool_data["code"],
            "description": tool_data["description"],
            "parameters": tool_data["parameters"]
        }
    
    tools.append(LLMTool(
        name="get_tool_code",
        description="Get the code and details for a stored tool. Use this to review or modify a tool.",
        parameters={
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Name of the tool"
                }
            },
            "required": ["tool_name"]
        },
        function=get_tool_code
    ))
    
    return tools

