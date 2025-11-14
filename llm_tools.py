"""
LLM Tool System - Allows the LLM to call functions/tools during generation.
Implements function calling similar to OpenAI's function calling API.
"""
from typing import List, Dict, Any, Optional, Callable, Union
import json
import re
from datetime import datetime
from logger_config import logger


class LLMTool:
    """Represents a tool/function that the LLM can call."""
    
    def __init__(self,
                 name: str,
                 description: str,
                 parameters: Dict[str, Any],
                 function: Callable):
        """
        Initialize an LLM tool.
        
        Args:
            name: Tool name (e.g., "get_user_gold")
            description: Tool description for the LLM
            parameters: JSON schema for parameters
            function: Python function to execute
        """
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function
    
    def execute(self, **kwargs) -> Any:
        """Execute the tool function."""
        try:
            return self.function(**kwargs)
        except Exception as e:
            logger.error(f"Error executing tool {self.name}: {e}", exc_info=True)
            return {"error": str(e)}


class LLMToolRegistry:
    """Registry of available tools for the LLM."""
    
    def __init__(self):
        """Initialize tool registry."""
        self.tools: Dict[str, LLMTool] = {}
    
    def register_tool(self, tool: LLMTool):
        """Register a tool."""
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[LLMTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def get_all_tools(self) -> List[LLMTool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Get JSON schema for all tools (for LLM)."""
        schemas = []
        for tool in self.tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return schemas


class LLMToolExecutor:
    """Executes tool calls from the LLM."""
    
    def __init__(self, tool_registry: LLMToolRegistry):
        """Initialize tool executor."""
        self.registry = tool_registry
        self.execution_history: List[Dict[str, Any]] = []
    
    def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool call.
        
        Args:
            tool_call: Dict with 'name' and 'arguments'
            
        Returns:
            Tool execution result
        """
        tool_name = tool_call.get("name")
        arguments = tool_call.get("arguments", {})
        
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except:
                arguments = {}
        
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return {
                "error": f"Tool '{tool_name}' not found",
                "tool_name": tool_name
            }
        
        try:
            result = tool.execute(**arguments)
            
            execution_record = {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            self.execution_history.append(execution_record)
            
            return {
                "tool_name": tool_name,
                "result": result
            }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {
                "error": str(e),
                "tool_name": tool_name
            }
    
    def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute multiple tool calls."""
        results = []
        for tool_call in tool_calls:
            result = self.execute_tool_call(tool_call)
            results.append(result)
        return results


class LLMToolParser:
    """Parses tool calls from LLM responses."""
    
    @staticmethod
    def parse_tool_calls(text: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from LLM text response.
        Supports multiple formats:
        1. JSON format: {"tool": "name", "arguments": {...}}
        2. Function call format: tool_name(arg1=value1, arg2=value2)
        3. Structured format: <tool_call>tool_name</tool_call><arguments>...</arguments>
        """
        tool_calls = []
        
        # Try JSON format first
        json_pattern = r'\{"tool":\s*"([^"]+)",\s*"arguments":\s*(\{.*?\})\}'
        json_matches = re.finditer(json_pattern, text, re.DOTALL)
        for match in json_matches:
            tool_name = match.group(1)
            try:
                arguments = json.loads(match.group(2))
                tool_calls.append({
                    "name": tool_name,
                    "arguments": arguments
                })
            except:
                pass
        
        # Try function call format: tool_name(arg1=value1, arg2="value2")
        func_pattern = r'(\w+)\s*\(([^)]*)\)'
        func_matches = re.finditer(func_pattern, text)
        for match in func_matches:
            tool_name = match.group(1)
            args_str = match.group(2)
            
            # Parse arguments
            arguments = {}
            if args_str.strip():
                # Simple argument parsing (key=value)
                arg_pattern = r'(\w+)\s*=\s*([^,]+)'
                for arg_match in re.finditer(arg_pattern, args_str):
                    key = arg_match.group(1)
                    value = arg_match.group(2).strip().strip('"\'')
                    # Try to convert to number
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except:
                        pass
                    arguments[key] = value
            
            tool_calls.append({
                "name": tool_name,
                "arguments": arguments
            })
        
        # Try structured XML-like format
        xml_pattern = r'<tool_call>\s*(\w+)\s*</tool_call>\s*<arguments>\s*(.*?)\s*</arguments>'
        xml_matches = re.finditer(xml_pattern, text, re.DOTALL)
        for match in xml_matches:
            tool_name = match.group(1)
            args_str = match.group(2)
            try:
                arguments = json.loads(args_str)
            except:
                arguments = {}
            tool_calls.append({
                "name": tool_name,
                "arguments": arguments
            })
        
        return tool_calls
    
    @staticmethod
    def format_tool_result(tool_name: str, result: Any) -> str:
        """Format tool result for LLM consumption."""
        if isinstance(result, dict):
            if "error" in result:
                return f"Error calling {tool_name}: {result['error']}"
            return json.dumps(result, indent=2)
        elif isinstance(result, (list, tuple)):
            return json.dumps(result, indent=2)
        else:
            return str(result)


def create_rag_tools(pipeline) -> LLMToolRegistry:
    """
    Create and register all RAG-related tools.
    
    Args:
        pipeline: EnhancedRAGPipeline instance
        
    Returns:
        Tool registry with all tools registered
    """
    registry = LLMToolRegistry()
    
    # Tool: Get user state (gold, inventory, etc.)
    def get_user_state(user_id: str, key: str = None) -> Dict[str, Any]:
        """Get user state (gold, inventory, or all state if key is None)."""
        if key:
            value = pipeline.state_manager.get_user_state(user_id, key)
            return {"user_id": user_id, "key": key, "value": value}
        else:
            all_state = pipeline.state_manager.get_user_all_states(user_id)
            return {"user_id": user_id, "state": all_state}
    
    registry.register_tool(LLMTool(
        name="get_user_state",
        description="Get a user's state (gold, inventory, level, etc.). Use this when asked about user balances, inventory, or stats.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Discord user ID"
                },
                "key": {
                    "type": "string",
                    "description": "State key (e.g., 'gold', 'inventory', 'level'). Leave null to get all state.",
                    "enum": ["gold", "coins", "silver", "inventory", "level", None]
                }
            },
            "required": ["user_id"]
        },
        function=get_user_state
    ))
    
    # Tool: Transfer state between users
    def transfer_state(from_user_id: str, to_user_id: str, key: str, amount: float) -> Dict[str, Any]:
        """Transfer state value (gold, coins, etc.) from one user to another."""
        result = pipeline.state_manager.transfer_state(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            key=key,
            amount=amount
        )
        return result
    
    registry.register_tool(LLMTool(
        name="transfer_state",
        description="Transfer state value (gold, coins, etc.) from one user to another. Use when user wants to give/take resources.",
        parameters={
            "type": "object",
            "properties": {
                "from_user_id": {
                    "type": "string",
                    "description": "Source user ID"
                },
                "to_user_id": {
                    "type": "string",
                    "description": "Destination user ID"
                },
                "key": {
                    "type": "string",
                    "description": "State key (e.g., 'gold', 'coins')",
                    "enum": ["gold", "coins", "silver"]
                },
                "amount": {
                    "type": "number",
                    "description": "Amount to transfer"
                }
            },
            "required": ["from_user_id", "to_user_id", "key", "amount"]
        },
        function=transfer_state
    ))
    
    # Tool: Transfer item
    def transfer_item(from_user_id: str, to_user_id: str, item: str, quantity: int = 1) -> Dict[str, Any]:
        """Transfer an item from one user's inventory to another."""
        result = pipeline.state_manager.transfer_item(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            item=item,
            quantity=quantity
        )
        return result
    
    registry.register_tool(LLMTool(
        name="transfer_item",
        description="Transfer an item from one user's inventory to another. Use when user wants to give/take items.",
        parameters={
            "type": "object",
            "properties": {
                "from_user_id": {
                    "type": "string",
                    "description": "Source user ID"
                },
                "to_user_id": {
                    "type": "string",
                    "description": "Destination user ID"
                },
                "item": {
                    "type": "string",
                    "description": "Item name"
                },
                "quantity": {
                    "type": "integer",
                    "description": "Quantity to transfer",
                    "default": 1
                }
            },
            "required": ["from_user_id", "to_user_id", "item"]
        },
        function=transfer_item
    ))
    
    # Tool: Set user state
    def set_user_state(user_id: str, key: str, value: Any) -> Dict[str, Any]:
        """Set a user's state value."""
        pipeline.state_manager.set_user_state(user_id, key, value)
        return {"success": True, "user_id": user_id, "key": key, "value": value}
    
    registry.register_tool(LLMTool(
        name="set_user_state",
        description="Set a user's state value (level, stats, etc.). Use when user wants to set or update a value.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User ID"
                },
                "key": {
                    "type": "string",
                    "description": "State key"
                },
                "value": {
                    "type": ["string", "number", "boolean"],
                    "description": "State value"
                }
            },
            "required": ["user_id", "key", "value"]
        },
        function=set_user_state
    ))
    
    # Tool: Search documents
    def search_documents(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search documents for information. Use when user asks about document content or needs information from documents."""
        query_embedding = pipeline.embedding_generator.generate_embedding(query)
        results = pipeline.enhanced_search.multi_stage_search(
            query=query,
            query_embedding=query_embedding,
            top_k=max_results
        )
        return results
    
    registry.register_tool(LLMTool(
        name="search_documents",
        description="Search documents for information. Use when user asks about document content, needs facts from documents, or asks informational questions.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 5
                },
                "doc_id": {
                    "type": "string",
                    "description": "Optional: Specific document ID to search"
                },
                "doc_filename": {
                    "type": "string",
                    "description": "Optional: Specific document filename to search"
                }
            },
            "required": ["query"]
        },
        function=search_documents
    ))
    
    # Tool: Get user profile
    def get_user_profile(user_id: str) -> Dict[str, Any]:
        """Get a user's profile and statistics."""
        profile = pipeline.user_relations.get_user_profile(user_id)
        return profile
    
    registry.register_tool(LLMTool(
        name="get_user_profile",
        description="Get a user's profile, preferences, and statistics. Use when asked about user information or preferences.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User ID"
                }
            },
            "required": ["user_id"]
        },
        function=get_user_profile
    ))
    
    # Tool: Get user relationships
    def get_user_relationships(user_id: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get a user's relationships with other users."""
        relationships = pipeline.user_relations.get_user_relationships(user_id, top_n)
        return relationships
    
    registry.register_tool(LLMTool(
        name="get_user_relationships",
        description="Get a user's relationships with other users. Use when asked about who a user interacts with or user connections.",
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User ID"
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of relationships to return",
                    "default": 10
                }
            },
            "required": ["user_id"]
        },
        function=get_user_relationships
    ))
    
    # Tool: Get relevant memories
    def get_memories(channel_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Get relevant memories from a channel. Use when user asks about past conversations or context."""
        query_embedding = pipeline.embedding_generator.generate_embedding(query)
        memories = pipeline.intelligent_memory.retrieve_with_context(
            channel_id=channel_id,
            query_embedding=query_embedding,
            top_k=top_k
        )
        return memories
    
    registry.register_tool(LLMTool(
        name="get_memories",
        description="Get relevant memories from a channel. Use when user asks about past conversations, context, or history.",
        parameters={
            "type": "object",
            "properties": {
                "channel_id": {
                    "type": "string",
                    "description": "Channel ID"
                },
                "query": {
                    "type": "string",
                    "description": "Query to find relevant memories"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of memories to return",
                    "default": 5
                }
            },
            "required": ["channel_id", "query"]
        },
        function=get_memories
    ))
    
    # Tool: List available documents
    def list_documents(limit: int = 20) -> List[Dict[str, Any]]:
        """List all available documents."""
        documents = pipeline.document_store.get_all_shared_documents()
        return documents[:limit]
    
    registry.register_tool(LLMTool(
        name="list_documents",
        description="List all available documents. Use when user asks what documents are available or wants to see document list.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of documents to return",
                    "default": 20
                }
            }
        },
        function=list_documents
    ))
    
    return registry

