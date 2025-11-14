"""
Tests for meta-tools (write_tool, test_tool, register_tool).
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.tools.meta_tools import create_meta_tools
from src.tools.tool_sandbox import ToolSandbox, ToolStorage
from src.tools.llm_tools import LLMToolRegistry


class TestMetaTools:
    """Test meta-tools functionality."""
    
    @pytest.mark.unit
    def test_create_meta_tools(self):
        """Test that meta-tools are created correctly."""
        sandbox = ToolSandbox()
        storage = ToolStorage()
        registry = LLMToolRegistry()
        
        meta_tools = create_meta_tools(sandbox, storage, registry)
        
        assert len(meta_tools) > 0
        tool_names = [tool.name for tool in meta_tools]
        assert "write_tool" in tool_names
        assert "test_tool" in tool_names
        assert "register_tool" in tool_names
    
    @pytest.mark.unit
    def test_write_tool_success(self, temp_dir):
        """Test writing a tool successfully."""
        sandbox = ToolSandbox()
        storage = ToolStorage(storage_dir=temp_dir)
        registry = LLMToolRegistry()
        
        meta_tools = create_meta_tools(sandbox, storage, registry)
        write_tool = next(tool for tool in meta_tools if tool.name == "write_tool")
        
        result = write_tool.function(
            code="def add(a, b): return a + b",
            function_name="add",
            description="Adds two numbers",
            parameters={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}}
        )
        
        assert result["success"] is True
        assert storage.get_tool("add") is not None
    
    @pytest.mark.unit
    def test_write_tool_invalid_code(self, temp_dir):
        """Test writing invalid code."""
        sandbox = ToolSandbox()
        storage = ToolStorage(storage_dir=temp_dir)
        registry = LLMToolRegistry()
        
        meta_tools = create_meta_tools(sandbox, storage, registry)
        write_tool = next(tool for tool in meta_tools if tool.name == "write_tool")
        
        result = write_tool.function(
            code="import os; os.system('rm -rf /')",
            function_name="dangerous",
            description="Dangerous function",
            parameters={}
        )
        
        assert result["success"] is False
    
    @pytest.mark.unit
    def test_test_tool(self, temp_dir):
        """Test testing a stored tool."""
        sandbox = ToolSandbox()
        storage = ToolStorage(storage_dir=temp_dir)
        registry = LLMToolRegistry()
        
        # First write a tool
        storage.store_tool("add", {
            "code": "def add(a, b): return a + b",
            "function_name": "add",
            "description": "Adds two numbers",
            "parameters": {}
        })
        
        meta_tools = create_meta_tools(sandbox, storage, registry)
        test_tool = next(tool for tool in meta_tools if tool.name == "test_tool")
        
        result = test_tool.function(
            tool_name="add",
            test_cases=[
                {"arguments": {"a": 2, "b": 3}, "expected_result": 5}
            ]
        )
        
        assert result["success"] is True
        assert result["passed"] > 0
    
    @pytest.mark.unit
    def test_register_tool(self, temp_dir):
        """Test registering a tool."""
        sandbox = ToolSandbox()
        storage = ToolStorage(storage_dir=temp_dir)
        registry = LLMToolRegistry()
        
        # Store and test a tool first
        storage.store_tool("add", {
            "code": "def add(a, b): return a + b",
            "function_name": "add",
            "description": "Adds two numbers",
            "parameters": {},
            "test_results": {"passed": 1, "failed": 0}
        })
        
        meta_tools = create_meta_tools(sandbox, storage, registry)
        register_tool = next(tool for tool in meta_tools if tool.name == "register_tool")
        
        result = register_tool.function(tool_name="add")
        
        assert result["success"] is True
        assert registry.get_tool("add") is not None

