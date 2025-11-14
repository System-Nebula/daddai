"""
Meta Tools - Tools that allow the LLM to create and test its own tools.
These are the foundational tools for self-extension.
"""
from typing import Dict, Any, List, Optional
from src.tools.tool_sandbox import ToolSandbox, ToolStorage
from src.tools.llm_tools import LLMTool, LLMToolRegistry
from logger_config import logger


def create_meta_tools(sandbox: ToolSandbox, storage: ToolStorage, registry: LLMToolRegistry, pipeline=None) -> List[LLMTool]:
    """
    Create meta-tools that allow LLM to create and test its own tools.
    
    Args:
        sandbox: Tool sandbox for safe execution
        storage: Tool storage for persistence
        registry: Tool registry to add new tools to
        pipeline: Enhanced pipeline instance (for accessing admin status)
        
    Returns:
        List of meta-tools
    """
    tools = []
    
    # Helper to check if current user is admin
    def is_admin_user() -> bool:
        """Check if current user is admin."""
        if pipeline and hasattr(pipeline, 'current_is_admin'):
            return pipeline.current_is_admin
        return False
    
    # Tool: Write a new tool
    def write_tool(code: str, function_name: str, description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write a new tool. The code should define a function with the given name.
        This tool is non-destructive - it only validates and stores the tool.
        Admin users can create tools with network access (requests, urllib).
        """
        # Check admin status for network requests
        admin_user = is_admin_user()
        
        # Check if code uses network requests (for non-admin users)
        uses_network = any(net in code.lower() for net in ['import requests', 'import urllib', 'requests.', 'urllib.'])
        if uses_network and not admin_user:
            return {
                "success": False,
                "error": "Network requests (requests, urllib) are only allowed for admin users. Please use API-less sources or contact an admin.",
                "hint": "For weather data, consider using API-less sources or ask an admin to create the tool."
            }
        
        # Validate code (allow network requests for admin users)
        validation = sandbox.validate_code(code, allow_network=admin_user)
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
        # Store admin status so network requests are allowed when testing/executing
        stored = storage.store_tool(
            tool_name=function_name,
            code=code,
            description=description,
            parameters=parameters,
            is_admin_tool=admin_user  # Store admin status
        )
        
        if not stored:
            return {
                "success": False,
                "error": f"Tool '{function_name}' already exists"
            }
        
        return {
            "success": True,
            "message": f"Tool '{function_name}' written and stored. Use test_tool to test it before registering. After testing and registering, users can reference this tool by name.",
            "tool_name": function_name,
            "next_steps": "1. Use test_tool to test the tool, 2. Use register_tool to make it available, 3. Inform the user about the tool name so they can reference it later"
        }
    
    tools.append(LLMTool(
        name="write_tool",
        description="Write a new tool/function. Provide Python code that defines a function. This is non-destructive - it only validates and stores the tool. Admin users can create tools with network access (requests, urllib). Non-admin users cannot use network requests. Use test_tool to test it before using. For weather tools, prefer API-less sources when possible.",
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
        # Check if tool was created by admin (allows network requests)
        is_admin_tool = tool_data.get("is_admin_tool", False)
        
        # Run tests (allow network if admin tool)
        test_results = sandbox.test_tool(
            code=code,
            function_name=tool_name,
            test_cases=test_cases,
            allow_network=is_admin_tool
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
            # Check if tool was created by admin (allows network requests)
            is_admin_tool = tool_data.get("is_admin_tool", False)
            
            # Execute code to get function (allow network for admin tools)
            exec_globals = {}
            if is_admin_tool:
                # Allow network modules for admin tools
                try:
                    import requests
                    exec_globals['requests'] = requests
                except ImportError:
                    pass
                try:
                    import urllib.request
                    import urllib.parse
                    exec_globals['urllib'] = type('urllib', (), {
                        'request': urllib.request,
                        'parse': urllib.parse
                    })()
                except ImportError:
                    pass
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
                "message": f"Tool '{tool_name}' registered successfully and is now available for use. Users can reference this tool by name: '{tool_name}'.",
                "tool_name": tool_name,
                "user_message": f"✅ Tool '{tool_name}' is now available! Users can reference it by asking about '{tool_name}' or using it in queries."
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
        # Check if tool was created by admin (allows network requests)
        is_admin_tool = tool_data.get("is_admin_tool", False)
        
        result = sandbox.execute_safely(
            code=tool_data["code"],
            function_name=tool_name,
            arguments=arguments,
            allow_network=is_admin_tool
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
    
    # Tool: List all available tools (registered + stored)
    def list_all_tools() -> Dict[str, Any]:
        """List all available tools (both registered and stored)."""
        # Get registered tools
        registered_tools = []
        for tool_name, tool in registry.tools.items():
            registered_tools.append({
                "name": tool_name,
                "description": tool.description,
                "status": "registered",
                "available": True
            })
        
        # Get stored tools
        stored_tool_names = storage.list_tools()
        stored_tools = []
        for name in stored_tool_names:
            # Skip if already registered
            if name in registry.tools:
                continue
            tool_data = storage.get_tool(name)
            stored_tools.append({
                "name": name,
                "description": tool_data.get("description"),
                "status": "stored",
                "tested": tool_data.get("test_results") is not None,
                "tests_passed": tool_data.get("test_results", {}).get("failed", 0) == 0 if tool_data.get("test_results") else None,
                "available": False  # Not registered yet
            })
        
        return {
            "registered_tools": registered_tools,
            "stored_tools": stored_tools,
            "total_registered": len(registered_tools),
            "total_stored": len(stored_tools),
            "total": len(registered_tools) + len(stored_tools)
        }
    
    tools.append(LLMTool(
        name="list_all_tools",
        description="List all available tools (both registered and stored). Registered tools are ready to use. Stored tools need to be tested and registered first. Use this to see what tools users can reference.",
        parameters={
            "type": "object",
            "properties": {}
        },
        function=list_all_tools
    ))
    
    return tools

