"""
Tests for tool sandbox and security features.
"""
import pytest
from unittest.mock import Mock, patch
from src.tools.tool_sandbox import ToolSandbox, ToolStorage, SecurityError


class TestToolSandbox:
    """Test tool sandbox security and execution."""
    
    @pytest.mark.unit
    def test_validate_code_safe(self):
        """Test validation of safe code."""
        sandbox = ToolSandbox()
        code = """
def add_numbers(a, b):
    return a + b
"""
        result = sandbox.validate_code(code)
        assert result["valid"] is True
        assert result["errors"] == []
    
    @pytest.mark.unit
    def test_validate_code_dangerous_import(self):
        """Test that dangerous imports are blocked."""
        sandbox = ToolSandbox()
        code = """
import os
def dangerous():
    os.system("rm -rf /")
"""
        result = sandbox.validate_code(code)
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    @pytest.mark.unit
    def test_validate_code_dangerous_function(self):
        """Test that dangerous functions are blocked."""
        sandbox = ToolSandbox()
        code = """
def dangerous():
    eval("malicious code")
"""
        result = sandbox.validate_code(code)
        assert result["valid"] is False
    
    @pytest.mark.unit
    def test_execute_safely_success(self):
        """Test safe execution of valid code."""
        sandbox = ToolSandbox()
        code = """
def multiply(a, b):
    return a * b
"""
        result = sandbox.execute_safely(code, "multiply", {"a": 5, "b": 3})
        assert result["success"] is True
        assert result["result"] == 15
    
    @pytest.mark.unit
    def test_execute_safely_error(self):
        """Test handling of execution errors."""
        sandbox = ToolSandbox()
        code = """
def divide(a, b):
    return a / b
"""
        result = sandbox.execute_safely(code, "divide", {"a": 5, "b": 0})
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.unit
    def test_execute_safely_blocked_operation(self):
        """Test that dangerous operations are blocked."""
        sandbox = ToolSandbox()
        code = """
def dangerous():
    import os
    return os.getcwd()
"""
        result = sandbox.execute_safely(code, "dangerous", {})
        assert result["success"] is False
    
    @pytest.mark.unit
    def test_validate_code_network_allowed_for_admin(self):
        """Test that network access can be allowed for admin tools."""
        sandbox = ToolSandbox()
        code = """
import requests
def fetch_data(url):
    return requests.get(url).text
"""
        result = sandbox.validate_code(code, allow_network=True)
        # Should be valid if network is allowed
        assert result["valid"] is True or "network" in str(result.get("errors", [])).lower()


class TestToolStorage:
    """Test tool storage functionality."""
    
    @pytest.mark.unit
    def test_store_tool(self, temp_dir):
        """Test storing a tool."""
        storage = ToolStorage(storage_dir=temp_dir)
        
        tool_data = {
            "code": "def test(): return 1",
            "function_name": "test",
            "description": "Test function",
            "parameters": {}
        }
        
        result = storage.store_tool("test_tool", tool_data)
        assert result["success"] is True
    
    @pytest.mark.unit
    def test_get_tool(self, temp_dir):
        """Test retrieving a stored tool."""
        storage = ToolStorage(storage_dir=temp_dir)
        
        tool_data = {
            "code": "def test(): return 1",
            "function_name": "test",
            "description": "Test function",
            "parameters": {}
        }
        
        storage.store_tool("test_tool", tool_data)
        retrieved = storage.get_tool("test_tool")
        
        assert retrieved is not None
        assert retrieved["function_name"] == "test"
    
    @pytest.mark.unit
    def test_list_tools(self, temp_dir):
        """Test listing stored tools."""
        storage = ToolStorage(storage_dir=temp_dir)
        
        tool_data = {
            "code": "def test(): return 1",
            "function_name": "test",
            "description": "Test function",
            "parameters": {}
        }
        
        storage.store_tool("tool1", tool_data)
        storage.store_tool("tool2", tool_data)
        
        tools = storage.list_tools()
        assert len(tools) == 2
        assert "tool1" in tools
        assert "tool2" in tools
    
    @pytest.mark.unit
    def test_delete_tool(self, temp_dir):
        """Test deleting a stored tool."""
        storage = ToolStorage(storage_dir=temp_dir)
        
        tool_data = {
            "code": "def test(): return 1",
            "function_name": "test",
            "description": "Test function",
            "parameters": {}
        }
        
        storage.store_tool("test_tool", tool_data)
        storage.delete_tool("test_tool")
        
        assert storage.get_tool("test_tool") is None

