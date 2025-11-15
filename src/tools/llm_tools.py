"""
LLM Tool System - Allows the LLM to call functions/tools during generation.
Implements function calling similar to OpenAI's function calling API.
"""
from typing import List, Dict, Any, Optional, Callable, Union
import json
import re
from datetime import datetime
from logger_config import logger
from src.tools.website_summarizer_tool import summarize_website


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
        self._schema_cache = None  # OPTIMIZED: Cache schema
    
    def register_tool(self, tool: LLMTool):
        """Register a tool. OPTIMIZED: Invalidate cache."""
        self.tools[tool.name] = tool
        self._schema_cache = None  # Invalidate cache
    
    def get_tool(self, name: str) -> Optional[LLMTool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def get_all_tools(self) -> List[LLMTool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        """Get JSON schema for all tools (for LLM). OPTIMIZED: Cached."""
        # Return cached schema if tools haven't changed
        if self._schema_cache is not None:
            return self._schema_cache
        
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
        
        self._schema_cache = schemas
        return schemas


class LLMToolExecutor:
    """Executes tool calls from the LLM."""
    
    def __init__(self, tool_registry: LLMToolRegistry):
        """Initialize tool executor."""
        self.registry = tool_registry
        self.execution_history: List[Dict[str, Any]] = []
        
        # OPTIMIZED: Add result caching
        from cachetools import TTLCache
        from config import CACHE_ENABLED, CACHE_TTL_SECONDS
        if CACHE_ENABLED:
            self.result_cache = TTLCache(maxsize=100, ttl=CACHE_TTL_SECONDS // 2)  # 30 min cache
        else:
            self.result_cache = {}
        
        # OPTIMIZED: Cache function signatures
        self._signature_cache = {}
    
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
        
        # Map common parameter aliases
        arguments = self._map_parameter_aliases(tool_name, arguments)
        
        # Log arguments after mapping for debugging
        logger.debug(f"Tool {tool_name} arguments after alias mapping: {list(arguments.keys())}")
        
        # OPTIMIZED: Check cache for cacheable tools
        cacheable_tools = ["summarize_youtube", "summarize_website", "search_documents", "get_memories"]
        if tool_name in cacheable_tools and self.result_cache:
            cache_key = self._get_tool_cache_key(tool_name, arguments)
            if cache_key in self.result_cache:
                logger.debug(f"Tool {tool_name} cache hit")
                cached_result = self.result_cache[cache_key].copy()
                cached_result["cached"] = True
                return cached_result
        
        # OPTIMIZED: Use cached signature
        import inspect
        valid_params = None
        if tool_name not in self._signature_cache:
            try:
                sig = inspect.signature(tool.function)
                valid_params = set(sig.parameters.keys())
                self._signature_cache[tool_name] = valid_params
            except Exception as e:
                logger.debug(f"Could not inspect function signature for {tool_name}: {e}")
                self._signature_cache[tool_name] = None
        else:
            valid_params = self._signature_cache[tool_name]
        
        # Filter arguments using cached signature
        if valid_params:
            logger.debug(f"Tool {tool_name} valid parameters from signature: {valid_params}")
            filtered_arguments = {k: v for k, v in arguments.items() if k in valid_params}
            
            # Log if we filtered anything (for debugging)
            filtered_out = set(arguments.keys()) - valid_params
            if filtered_out:
                # Don't warn for generate_image - we intentionally filter out user_id/channel_id
                if tool_name != "generate_image":
                    logger.warning(f"⚠️ Filtered out unexpected parameters for {tool_name}: {filtered_out}. Valid params: {valid_params}")
                else:
                    logger.debug(f"Filtered out context parameters for {tool_name}: {filtered_out}")
            
            arguments = filtered_arguments
            logger.debug(f"Tool {tool_name} arguments after filtering: {list(arguments.keys())}")
        
        # Validate required parameters
        required_params = tool.parameters.get("required", [])
        missing_params = [p for p in required_params if p not in arguments]
        if missing_params:
            logger.error(f"❌ Tool {tool_name} validation failed. Required: {required_params}, Provided: {list(arguments.keys())}, Missing: {missing_params}")
            return {
                "error": f"Missing required parameters: {', '.join(missing_params)}",
                "tool_name": tool_name,
                "required": required_params,
                "provided": list(arguments.keys()),
                "debug_info": {
                    "arguments_after_mapping": list(self._map_parameter_aliases(tool_name, tool_call.get("arguments", {})).keys()),
                    "valid_signature_params": list(valid_params) if 'valid_params' in locals() else "unknown"
                }
            }
        
        try:
            # Enhanced error recovery: try with default values for optional parameters
            result = tool.execute(**arguments)
            
            execution_record = {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            self.execution_history.append(execution_record)
            
            tool_result = {
                "tool_name": tool_name,
                "result": result
            }
            
            # OPTIMIZED: Cache result for cacheable tools
            if tool_name in cacheable_tools and self.result_cache and "error" not in result:
                cache_key = self._get_tool_cache_key(tool_name, arguments)
                self.result_cache[cache_key] = tool_result.copy()
            
            return tool_result
        except TypeError as e:
            # Enhanced error recovery: try to infer missing parameters from context
            error_msg = str(e)
            if "missing" in error_msg.lower() or "required" in error_msg.lower():
                # Try to extract missing parameter from error message
                import re
                missing_match = re.search(r"missing (\d+) required", error_msg)
                if missing_match:
                    logger.warning(f"Tool {tool_name} missing required parameters. Attempting recovery...")
                    # Could add smart parameter inference here in the future
            # Parameter mismatch error - provide helpful message
            import inspect
            try:
                sig = inspect.signature(tool.function)
                expected_params = list(sig.parameters.keys())
                error_msg = f"Parameter mismatch. Expected: {', '.join(expected_params)}, Got: {', '.join(arguments.keys())}"
                logger.error(f"Parameter mismatch for tool {tool_name}: {e}. {error_msg}")
                return {
                    "error": error_msg,
                    "tool_name": tool_name,
                    "expected": expected_params,
                    "provided": list(arguments.keys())
                }
            except:
                logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                return {
                    "error": str(e),
                    "tool_name": tool_name
                }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return {
                "error": str(e),
                "tool_name": tool_name
            }
    
    def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute multiple tool calls.
        OPTIMIZED: Execute independent tools in parallel.
        """
        if len(tool_calls) == 1:
            return [self.execute_tool_call(tool_calls[0])]
        
        # Group tools by dependencies
        # Tools that can run in parallel vs those that depend on others
        independent_tools = []
        dependent_tools = []
        
        # URL tools should run sequentially (to avoid duplicate fetches)
        # Other tools can run in parallel
        url_tools = ["summarize_youtube", "summarize_website"]
        
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            if tool_name in url_tools:
                dependent_tools.append(tool_call)
            else:
                independent_tools.append(tool_call)
        
        results = []
        
        # Execute independent tools in parallel
        if independent_tools:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=min(5, len(independent_tools))) as executor:
                futures = {
                    executor.submit(self.execute_tool_call, tool_call): idx
                    for idx, tool_call in enumerate(independent_tools)
                }
                
                independent_results = [None] * len(independent_tools)
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        independent_results[idx] = future.result(timeout=30)
                    except Exception as e:
                        logger.error(f"Error executing independent tool {idx}: {e}")
                        independent_results[idx] = {
                            "error": str(e),
                            "tool_name": independent_tools[idx].get("name", "unknown")
                        }
                
                results.extend(independent_results)
        
        # Execute dependent tools sequentially (URL tools, etc.)
        for tool_call in dependent_tools:
            try:
                result = self.execute_tool_call(tool_call)
                results.append(result)
            except Exception as e:
                logger.error(f"Error executing dependent tool: {e}")
                results.append({
                    "error": str(e),
                    "tool_name": tool_call.get("name", "unknown")
                })
        
        return results
    
    def _get_tool_cache_key(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Generate cache key for tool call."""
        import hashlib
        import json
        
        # Normalize arguments for cache key
        cache_data = {
            "tool": tool_name,
            "args": sorted(arguments.items())
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _map_parameter_aliases(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map common parameter aliases to correct parameter names.
        Handles cases where LLM uses different parameter names.
        Enhanced with smarter mapping and context awareness.
        """
        mapped = arguments.copy()
        
        # Enhanced alias mapping with context awareness
        # Maps common LLM parameter names to actual function parameter names
        alias_mappings = {
            "summarize_youtube": {
                "url": ["video_url", "youtube_url", "video", "link", "youtube_link", "videoUrl"],  # LLM might use video_url, map to url
                "language_codes": ["languages", "lang", "langs", "language", "languageCodes"],
                "save_to_documents": ["save", "store", "persist", "saveToDocuments"]
            },
            "summarize_website": {
                "url": ["website_url", "link", "web_url", "site_url", "websiteUrl"],  # Map various URL names to url
                "save_to_documents": ["save", "store", "persist", "saveToDocuments"]
            },
            "search_documents": {
                "query": ["question", "search", "search_query", "q", "searchQuery"],
                "max_results": ["top_k", "k", "limit", "num_results", "count", "maxResults", "topK"]
            },
            "get_user_state": {
                "user_id": ["user", "userId", "user_id", "target_user", "userId"],  # Map various user ID names
                "key": ["state_key", "property", "field", "stateKey"]
            }
        }
        
        # Apply tool-specific mappings
        # This maps LLM-provided aliases to the correct parameter names expected by the function
        if tool_name in alias_mappings:
            for correct_param, aliases in alias_mappings[tool_name].items():
                for alias in aliases:
                    if alias in mapped and correct_param not in mapped:
                        mapped[correct_param] = mapped.pop(alias)
                        logger.debug(f"Mapped parameter '{alias}' -> '{correct_param}' for tool {tool_name}")
        
        # Parameter alias mappings
        aliases = {
            "search_documents": {
                "q": "query",
                "question": "query",
                "search": "query"
            },
            "get_memories": {
                "q": "query",
                "question": "query",
                "search": "query"
            },
            "get_user_state": {
                "user": "user_id",
                "uid": "user_id"
            },
            "get_user_profile": {
                "user": "user_id",
                "uid": "user_id"
            },
            "get_user_relationships": {
                "user": "user_id",
                "uid": "user_id"
            },
            "transfer_state": {
                "from_user": "from_user_id",
                "to_user": "to_user_id",
                "from": "from_user_id",
                "to": "to_user_id"
            },
            "transfer_item": {
                "from_user": "from_user_id",
                "to_user": "to_user_id",
                "from": "from_user_id",
                "to": "to_user_id"
            }
        }
        
        # Apply aliases for this tool
        if tool_name in aliases:
            for alias, correct_name in aliases[tool_name].items():
                if alias in mapped and correct_name not in mapped:
                    mapped[correct_name] = mapped.pop(alias)
        
        return mapped


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
        
        # Try JSON format first - be more lenient with whitespace
        # Pattern 1: {"tool": "name", "arguments": {...}}
        json_pattern = r'\{"tool"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\}'
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
        
        # Pattern 2: {"tool":"name","arguments":{...}} (no spaces)
        json_pattern2 = r'\{"tool":"([^"]+)","arguments":(\{.*?\})\}'
        json_matches2 = re.finditer(json_pattern2, text, re.DOTALL)
        for match in json_matches2:
            tool_name = match.group(1)
            try:
                arguments = json.loads(match.group(2))
                tool_calls.append({
                    "name": tool_name,
                    "arguments": arguments
                })
            except:
                pass
        
        # Pattern 3: Look for JSON blocks that might be tool calls (more lenient)
        # Try to find any JSON object that has "tool" and "arguments" keys
        json_block_pattern = r'\{[^{}]*"tool"\s*:\s*"([^"]+)"[^{}]*"arguments"\s*:\s*(\{.*?\})[^{}]*\}'
        json_block_matches = re.finditer(json_block_pattern, text, re.DOTALL)
        for match in json_block_matches:
            tool_name = match.group(1)
            try:
                # Try to extract the full JSON object
                start = match.start()
                end = text.find('}', start) + 1
                json_str = text[start:end]
                parsed = json.loads(json_str)
                if "tool" in parsed and "arguments" in parsed:
                    tool_calls.append({
                        "name": parsed["tool"],
                        "arguments": parsed["arguments"]
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
            # Check for errors at multiple levels
            if "error" in result:
                error_msg = result['error']
                logger.error(f"❌ Tool {tool_name} error: {error_msg}")
                return f"ERROR: Tool {tool_name} failed: {error_msg}\n\nPlease inform the user that the tool encountered an error and cannot complete the request."
            
            # Check if result has nested error
            if result.get("result") and isinstance(result.get("result"), dict) and "error" in result.get("result"):
                error_msg = result["result"]['error']
                logger.error(f"❌ Tool {tool_name} nested error: {error_msg}")
                return f"ERROR: Tool {tool_name} failed: {error_msg}\n\nPlease inform the user that the tool encountered an error and cannot complete the request."
            
            # Special formatting for YouTube transcripts - make transcript content prominent
            if tool_name == "summarize_youtube" and "transcript" in result:
                transcript = result.get("transcript", "")
                video_id = result.get("video_id", "unknown")
                url = result.get("url", "")
                language = result.get("language", "unknown")
                transcript_length = result.get("transcript_length", 0)
                smart_summary = result.get("smart_summary")
                has_smart_summary = result.get("has_smart_summary", False)
                
                # CRITICAL: Make it very clear this is SUCCESS
                formatted = f"✅✅✅ SUCCESS: YouTube Video Transcript Successfully Fetched! ✅✅✅\n\n"
                formatted += f"YouTube Video Transcript (Video ID: {video_id}, URL: {url})\n"
                formatted += f"Language: {language}\n"
                formatted += f"Transcript Length: {transcript_length} characters\n"
                formatted += f"Status: SUCCESS - Transcript is available below!\n\n"
                
                # Use smart summary if available (for large transcripts)
                if has_smart_summary and smart_summary:
                    formatted += "\n" + "=" * 80 + "\n"
                    formatted += "🎯🎯🎯 VIDEO CONTENT IS BELOW - READ IT NOW! 🎯🎯🎯\n"
                    formatted += "=" * 80 + "\n"
                    formatted += "SMART SUMMARY (Intelligently chunked and summarized):\n"
                    formatted += "=" * 80 + "\n\n"
                    formatted += smart_summary
                    formatted += "\n\n" + "=" * 80 + "\n"
                    formatted += f"\n✅✅✅ CRITICAL: The summary above contains the ACTUAL VIDEO CONTENT!\n"
                    formatted += f"✅✅✅ The tool SUCCEEDED - there was NO ERROR!\n"
                    formatted += f"✅✅✅ You MUST use the summary above to answer the user's question!\n"
                    formatted += f"✅✅✅ Do NOT say there was an error - the content is RIGHT THERE above!\n"
                    formatted += f"\n📝 This is a smart summary of the full transcript ({transcript_length} characters). "
                    formatted += f"The summary covers all key topics and important information from the video.\n"
                else:
                    # Use full transcript (or truncated if too long)
                    formatted += "\n" + "=" * 80 + "\n"
                    formatted += "🎯🎯🎯 VIDEO CONTENT IS BELOW - READ IT NOW! 🎯🎯🎯\n"
                    formatted += "=" * 80 + "\n"
                    formatted += "TRANSCRIPT CONTENT (READ THIS TO ANSWER THE USER'S QUESTION):\n"
                    formatted += "=" * 80 + "\n\n"
                    formatted += transcript[:50000]  # Limit to 50k chars to avoid token limits
                    if len(transcript) > 50000:
                        formatted += "\n\n... [transcript truncated - full transcript is " + str(len(transcript)) + " characters]"
                    formatted += "\n\n" + "=" * 80 + "\n"
                    formatted += f"\n✅✅✅ CRITICAL: The transcript above contains the ACTUAL VIDEO CONTENT!\n"
                    formatted += f"✅✅✅ The tool SUCCEEDED - there was NO ERROR!\n"
                    formatted += f"✅✅✅ You MUST use the transcript above to answer the user's question!\n"
                    formatted += f"✅✅✅ Do NOT say there was an error - the content is RIGHT THERE above!\n"
                
                # Add metadata at the end
                if result.get("existing_document"):
                    formatted += f"\nNote: This transcript already exists in document store (doc_id: {result.get('doc_id')}).\n"
                elif result.get("saved_to_documents"):
                    formatted += f"\nNote: Transcript saved to document store (doc_id: {result.get('doc_id')}).\n"
                
                return formatted
            
            # Special formatting for website content - make full_text prominent
            if tool_name == "summarize_website" and "full_text" in result:
                full_text = result.get("full_text", "")
                title = result.get("title", "Untitled")
                url = result.get("url", "")
                metadata = result.get("metadata", {})
                text_length = result.get("text_length", 0)
                smart_summary = result.get("smart_summary")
                has_smart_summary = result.get("has_smart_summary", False)
                
                formatted = f"✅✅✅ SUCCESS: Website Article Successfully Fetched! ✅✅✅\n\n"
                formatted += f"Article Title: {title}\n"
                formatted += f"URL: {url}\n"
                if metadata.get('author'):
                    formatted += f"Author: {metadata.get('author')}\n"
                if metadata.get('date'):
                    formatted += f"Date: {metadata.get('date')}\n"
                formatted += f"Content Length: {text_length} characters\n"
                formatted += f"Status: SUCCESS - Article content is available below!\n\n"
                
                # Use smart summary if available (for large articles)
                if has_smart_summary and smart_summary:
                    formatted += "=" * 80 + "\n"
                    formatted += "SMART SUMMARY (Intelligently chunked and summarized):\n"
                    formatted += "=" * 80 + "\n\n"
                    formatted += smart_summary
                    formatted += "\n\n" + "=" * 80 + "\n"
                    formatted += f"\n📝 Note: This is a smart summary of the full article ({text_length} characters). "
                    formatted += f"The summary covers all key topics and important information from the article.\n"
                else:
                    # Use full article (or truncated if too long)
                    formatted += "=" * 80 + "\n"
                    formatted += "ARTICLE CONTENT (READ THIS TO ANSWER THE USER'S QUESTION):\n"
                    formatted += "=" * 80 + "\n\n"
                    formatted += full_text[:50000]  # Limit to 50k chars to avoid token limits
                    if len(full_text) > 50000:
                        formatted += "\n\n... [content truncated - full article is " + str(len(full_text)) + " characters]"
                    formatted += "\n\n" + "=" * 80 + "\n"
                
                formatted += f"\n✅ IMPORTANT: The content above contains the actual article content. Use it to answer the user's question. Do NOT say there was an error - the article was successfully fetched!\n"
                
                # Add metadata
                if result.get("existing_document"):
                    formatted += f"\nNote: This content already exists in document store (doc_id: {result.get('doc_id')}).\n"
                elif result.get("saved_to_documents"):
                    formatted += f"\nNote: Content saved to document store (doc_id: {result.get('doc_id')}).\n"
                
                return formatted
            
            # Special formatting for image generation
            if tool_name == "generate_image":
                if result.get("success"):
                    image_path = result.get("image_path", "")
                    filename = result.get("filename", "generated_image.png")
                    prompt = result.get("prompt", "")
                    
                    formatted = f"✅✅✅ SUCCESS: Image Generated Successfully! ✅✅✅\n\n"
                    formatted += f"**Prompt:** {prompt}\n"
                    formatted += f"**Image Path:** {image_path}\n"
                    formatted += f"**Filename:** {filename}\n"
                    formatted += f"\n🎨 The image has been generated and saved. The image file path is: {image_path}\n"
                    formatted += f"📎 IMPORTANT: The bot should attach this image file to the Discord message.\n"
                    
                    # Include metadata
                    if result.get("width"):
                        formatted += f"**Dimensions:** {result.get('width')}x{result.get('height')}\n"
                    if result.get("steps"):
                        formatted += f"**Steps:** {result.get('steps')}\n"
                    if result.get("seed"):
                        formatted += f"**Seed:** {result.get('seed')}\n"
                    
                    return formatted
                else:
                    error_msg = result.get("error", "Unknown error")
                    return f"❌ Image generation failed: {error_msg}\n\nPlease inform the user that the image could not be generated."
            
            # Default: return JSON for other tools
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
    def search_documents(query: str, max_results: int = 5, doc_id: Optional[str] = None, doc_filename: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search documents for information. Use when user asks about document content or needs information from documents."""
        query_embedding = pipeline.embedding_generator.generate_embedding(query)
        results = pipeline.enhanced_search.multi_stage_search(
            query=query,
            query_embedding=query_embedding,
            top_k=max_results,
            doc_id=doc_id,
            doc_filename=doc_filename
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
    
    # Tool: Summarize website
    def summarize_website_wrapper(url: str, max_length: int = 50000, save_to_documents: bool = True, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Wrapper that provides pipeline dependencies to summarize_website.
        Intelligently checks for existing documents first, only fetches if needed.
        """
        from src.tools.website_summarizer_tool import summarize_website
        # NOTE: DocumentProcessor and EmbeddingGenerator are imported lazily only when needed
        # to avoid DLL loading errors when docling isn't required
        
        # Get user_id from pipeline context if available
        user_id = None
        if pipeline and hasattr(pipeline, 'current_user_id'):
            user_id = pipeline.current_user_id
        
        # Get document store, embedding generator, and processor
        doc_store = pipeline.document_store if pipeline else None
        
        # Check if document already exists (for logging, but always fetch content for LLM)
        existing_doc = None
        if doc_store and not force_refresh:
            try:
                # Try to find existing document by URL
                if hasattr(doc_store, 'find_document_by_url'):
                    existing_doc = doc_store.find_document_by_url(url)
                    if existing_doc:
                        logger.info(f"📄 Found existing document for {url}: {existing_doc['id']} (will still fetch content for summary)")
            except Exception as e:
                logger.debug(f"Could not check for existing document: {e}")
        
        # Initialize document processing components (always if doc_store available, for caching)
        # IMPORTANT: Only import DocumentProcessor/EmbeddingGenerator if doc_store is available
        # This avoids DLL loading errors when docling isn't needed
        embedding_gen = None
        doc_processor = None
        
        if doc_store:  # Always initialize if doc_store is available (for caching)
            try:
                # Lazy import - only import when actually needed
                from src.processors.embedding_generator import EmbeddingGenerator
                from config import CHUNK_SIZE, CHUNK_OVERLAP, USE_GPU, EMBEDDING_BATCH_SIZE
                
                # Initialize embedding generator
                device = USE_GPU if USE_GPU != 'auto' else None
                embedding_gen = EmbeddingGenerator(device=device, batch_size=EMBEDDING_BATCH_SIZE)
                
                # For website/YouTube content, we only need simple markdown processing (no docling needed)
                # Create a simple markdown processor that doesn't require docling
                class SimpleMarkdownProcessor:
                    def __init__(self, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
                        self.chunk_size = chunk_size
                        self.chunk_overlap = chunk_overlap
                    
                    def process_document(self, file_path: str):
                        """Process markdown file without docling (perfect for website/YouTube content)."""
                        import os
                        import re
                        from datetime import datetime
                        
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            text = f.read()
                        
                        # Better chunking: handle both double newlines and single newlines
                        # Also handle YouTube transcripts which might be continuous text
                        chunks = []
                        
                        # Remove markdown headers to get to the actual content
                        # Extract transcript/content section if it exists
                        content_section = text
                        if "## Transcript" in text:
                            content_section = text.split("## Transcript")[-1].strip()
                        elif "# YouTube Video Transcript" in text or "# " in text:
                            # Skip header lines
                            lines = text.split('\n')
                            content_start = 0
                            for i, line in enumerate(lines):
                                if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('**') and not line.strip().startswith('---'):
                                    content_start = i
                                    break
                            content_section = '\n'.join(lines[content_start:]).strip()
                        
                        # First try splitting by double newlines (paragraphs)
                        paragraphs = re.split(r'\n\s*\n', content_section)
                        
                        # If that doesn't create enough chunks, split by sentences instead
                        if len(paragraphs) < 3 or (len(content_section) > self.chunk_size * 3 and len(paragraphs) < len(content_section) / self.chunk_size):
                            # Split by sentences (periods, exclamation, question marks followed by space)
                            sentences = re.split(r'(?<=[.!?])\s+', content_section)
                            # Group sentences into chunks
                            current_chunk = ""
                            chunk_index = 0
                            
                            for sentence in sentences:
                                sentence = sentence.strip()
                                if not sentence or len(sentence) < 5:
                                    continue
                                
                                # If adding this sentence would exceed chunk_size, save current chunk
                                if len(current_chunk) + len(sentence) + 2 > self.chunk_size and current_chunk:
                                    chunks.append({
                                        'text': current_chunk.strip(),
                                        'chunk_index': chunk_index
                                    })
                                    chunk_index += 1
                                    # Start new chunk with overlap
                                    overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                                    current_chunk = overlap_text + ' ' + sentence
                                else:
                                    current_chunk += ' ' + sentence if current_chunk else sentence
                            
                            if current_chunk:
                                chunks.append({
                                    'text': current_chunk.strip(),
                                    'chunk_index': chunk_index
                                })
                        else:
                            # Use paragraph-based chunking
                            current_chunk = ""
                            chunk_index = 0
                            
                            for para in paragraphs:
                                para = para.strip()
                                if not para or len(para) < 10:  # Skip very short paragraphs
                                    continue
                                
                                # If paragraph itself is larger than chunk_size, split it further
                                if len(para) > self.chunk_size:
                                    # Split large paragraph by sentences
                                    sentences = re.split(r'(?<=[.!?])\s+', para)
                                    for sentence in sentences:
                                        sentence = sentence.strip()
                                        if not sentence:
                                            continue
                                        
                                        if len(current_chunk) + len(sentence) + 2 > self.chunk_size and current_chunk:
                                            chunks.append({
                                                'text': current_chunk.strip(),
                                                'chunk_index': chunk_index
                                            })
                                            chunk_index += 1
                                            # Start new chunk with overlap
                                            overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                                            current_chunk = overlap_text + ' ' + sentence
                                        else:
                                            current_chunk += ' ' + sentence if current_chunk else sentence
                                else:
                                    # Normal paragraph processing
                                    if len(current_chunk) + len(para) + 2 > self.chunk_size and current_chunk:
                                        chunks.append({
                                            'text': current_chunk.strip(),
                                            'chunk_index': chunk_index
                                        })
                                        chunk_index += 1
                                        # Start new chunk with overlap
                                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                                        current_chunk = overlap_text + '\n\n' + para
                                    else:
                                        current_chunk += '\n\n' + para if current_chunk else para
                            
                            if current_chunk:
                                chunks.append({
                                    'text': current_chunk.strip(),
                                    'chunk_index': chunk_index
                                })
                        
                        logger.info(f"📝 Created {len(chunks)} chunks from document ({len(text)} chars, content section: {len(content_section)} chars)")
                        
                        return {
                            'text': text,
                            'chunks': chunks,
                            'metadata': {
                                'file_name': os.path.basename(file_path),
                                'file_path': file_path,
                                'file_type': '.md',
                                'processed_at': datetime.now().isoformat()
                            }
                        }
                
                doc_processor = SimpleMarkdownProcessor(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
                logger.debug(f"✅ Using simple markdown processor for website content (no docling needed)")
            except Exception as e:
                logger.error(f"❌ CRITICAL: Failed to initialize document processing components: {e}")
                logger.error(f"   Documents will NOT be saved to Neo4j/Elasticsearch.")
                # Continue without saving - we can still return the content
        
        # Let the tool function handle checking for existing documents and saving
        # Always pass components if available so tool can check cache and save new content
        result = summarize_website(
            url=url,
            max_length=max_length,
            save_to_documents=save_to_documents,  # Tool will handle caching logic
            user_id=user_id or "system",
            document_store=doc_store if (embedding_gen is not None and doc_processor is not None) else None,
            embedding_generator=embedding_gen,
            document_processor=doc_processor
        )
        
        return result
    
    registry.register_tool(LLMTool(
        name="summarize_website",
        description="Fetch a website URL and intelligently extract structured article content. IMPORTANT: This tool ALWAYS fetches the website content (even if it's already saved) so you can summarize it. It checks if the content already exists in the document store, but still fetches and returns the content for summarization. Automatically saves new content to the document store for RAG queries. Use this when users ask about, summarize, or want information from a website URL. The tool can fetch ANY information from websites and makes it searchable via RAG.",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Website URL to fetch and extract content from (e.g., 'https://example.com/article')"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum length of extracted text in characters (default: 50000)",
                    "default": 50000
                },
                "save_to_documents": {
                    "type": "boolean",
                    "description": "Whether to save the website content to the document store for RAG queries (default: true)",
                    "default": True
                },
                "force_refresh": {
                    "type": "boolean",
                    "description": "Force refresh even if document already exists (default: false)",
                    "default": False
                }
            },
            "required": ["url"]
        },
        function=summarize_website_wrapper
    ))
    
    # Tool: Summarize YouTube video
    def summarize_youtube_wrapper(url: str, language_codes: list = None, save_to_documents: bool = True, force_refresh: bool = False, user_id: str = None, channel_id: str = None) -> Dict[str, Any]:
        """
        Wrapper that provides pipeline dependencies to summarize_youtube.
        Intelligently checks for existing documents first, only fetches if needed.
        
        Args:
            url: YouTube video URL or video ID
            language_codes: Optional list of language codes to try
            save_to_documents: Whether to save transcript to document store
            force_refresh: Force refresh even if transcript exists
            user_id: Optional user ID (can be passed by LLM or extracted from context)
            channel_id: Optional channel ID (can be passed by LLM, currently unused but accepted)
        """
        from src.tools.youtube_transcript_tool import summarize_youtube, extract_video_id
        # NOTE: DocumentProcessor and EmbeddingGenerator are imported lazily only when needed
        # to avoid DLL loading errors when docling isn't required
        
        # Get user_id from parameter or pipeline context if available
        if not user_id and pipeline and hasattr(pipeline, 'current_user_id'):
            user_id = pipeline.current_user_id
        
        # Get document store, embedding generator, and processor
        doc_store = pipeline.document_store if pipeline else None
        
        # Extract video ID for checking existing documents
        video_id = extract_video_id(url)
        video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else url
        
        # Check if document already exists (for logging, but always fetch transcript for LLM)
        existing_doc = None
        if doc_store and video_id and not force_refresh:
            try:
                # Try to find existing document by URL
                if hasattr(doc_store, 'find_document_by_url'):
                    existing_doc = doc_store.find_document_by_url(video_url)
                    if existing_doc:
                        logger.info(f"📄 Found existing document for YouTube video {video_id}: {existing_doc['id']} (will still fetch transcript for summary)")
            except Exception as e:
                logger.debug(f"Could not check for existing document: {e}")
        
        # Initialize document processing components (always if doc_store available, for caching)
        # IMPORTANT: Only import DocumentProcessor/EmbeddingGenerator if doc_store is available
        # This avoids DLL loading errors when docling isn't needed
        embedding_gen = None
        doc_processor = None
        
        if doc_store:  # Always initialize if doc_store is available (for caching)
            try:
                # Lazy import - only import when actually needed
                from src.processors.embedding_generator import EmbeddingGenerator
                from config import CHUNK_SIZE, CHUNK_OVERLAP, USE_GPU, EMBEDDING_BATCH_SIZE
                
                # Initialize embedding generator
                device = USE_GPU if USE_GPU != 'auto' else None
                embedding_gen = EmbeddingGenerator(device=device, batch_size=EMBEDDING_BATCH_SIZE)
                
                # For YouTube transcripts, we only need simple markdown processing (no docling needed)
                # Create a simple markdown processor that doesn't require docling
                class SimpleMarkdownProcessor:
                    def __init__(self, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
                        self.chunk_size = chunk_size
                        self.chunk_overlap = chunk_overlap
                    
                    def process_document(self, file_path: str):
                        """Process markdown file without docling (perfect for YouTube transcripts)."""
                        import os
                        import re
                        from datetime import datetime
                        
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            text = f.read()
                        
                        # Better chunking: handle both double newlines and single newlines
                        # Also handle YouTube transcripts which might be continuous text
                        chunks = []
                        
                        # Remove markdown headers to get to the actual content
                        # Extract transcript/content section if it exists
                        content_section = text
                        if "## Transcript" in text:
                            content_section = text.split("## Transcript")[-1].strip()
                        elif "# YouTube Video Transcript" in text or "# " in text:
                            # Skip header lines
                            lines = text.split('\n')
                            content_start = 0
                            for i, line in enumerate(lines):
                                if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('**') and not line.strip().startswith('---'):
                                    content_start = i
                                    break
                            content_section = '\n'.join(lines[content_start:]).strip()
                        
                        # First try splitting by double newlines (paragraphs)
                        paragraphs = re.split(r'\n\s*\n', content_section)
                        
                        # If that doesn't create enough chunks, split by sentences instead
                        if len(paragraphs) < 3 or (len(content_section) > self.chunk_size * 3 and len(paragraphs) < len(content_section) / self.chunk_size):
                            # Split by sentences (periods, exclamation, question marks followed by space)
                            sentences = re.split(r'(?<=[.!?])\s+', content_section)
                            # Group sentences into chunks
                            current_chunk = ""
                            chunk_index = 0
                            
                            for sentence in sentences:
                                sentence = sentence.strip()
                                if not sentence or len(sentence) < 5:
                                    continue
                                
                                # If adding this sentence would exceed chunk_size, save current chunk
                                if len(current_chunk) + len(sentence) + 2 > self.chunk_size and current_chunk:
                                    chunks.append({
                                        'text': current_chunk.strip(),
                                        'chunk_index': chunk_index
                                    })
                                    chunk_index += 1
                                    # Start new chunk with overlap
                                    overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                                    current_chunk = overlap_text + ' ' + sentence
                                else:
                                    current_chunk += ' ' + sentence if current_chunk else sentence
                            
                            if current_chunk:
                                chunks.append({
                                    'text': current_chunk.strip(),
                                    'chunk_index': chunk_index
                                })
                        else:
                            # Use paragraph-based chunking
                            current_chunk = ""
                            chunk_index = 0
                            
                            for para in paragraphs:
                                para = para.strip()
                                if not para or len(para) < 10:  # Skip very short paragraphs
                                    continue
                                
                                # If paragraph itself is larger than chunk_size, split it further
                                if len(para) > self.chunk_size:
                                    # Split large paragraph by sentences
                                    sentences = re.split(r'(?<=[.!?])\s+', para)
                                    for sentence in sentences:
                                        sentence = sentence.strip()
                                        if not sentence:
                                            continue
                                        
                                        if len(current_chunk) + len(sentence) + 2 > self.chunk_size and current_chunk:
                                            chunks.append({
                                                'text': current_chunk.strip(),
                                                'chunk_index': chunk_index
                                            })
                                            chunk_index += 1
                                            # Start new chunk with overlap
                                            overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                                            current_chunk = overlap_text + ' ' + sentence
                                        else:
                                            current_chunk += ' ' + sentence if current_chunk else sentence
                                else:
                                    # Normal paragraph processing
                                    if len(current_chunk) + len(para) + 2 > self.chunk_size and current_chunk:
                                        chunks.append({
                                            'text': current_chunk.strip(),
                                            'chunk_index': chunk_index
                                        })
                                        chunk_index += 1
                                        # Start new chunk with overlap
                                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                                        current_chunk = overlap_text + '\n\n' + para
                                    else:
                                        current_chunk += '\n\n' + para if current_chunk else para
                            
                            if current_chunk:
                                chunks.append({
                                    'text': current_chunk.strip(),
                                    'chunk_index': chunk_index
                                })
                        
                        logger.info(f"📝 Created {len(chunks)} chunks from document ({len(text)} chars, content section: {len(content_section)} chars)")
                        
                        return {
                            'text': text,
                            'chunks': chunks,
                            'metadata': {
                                'file_name': os.path.basename(file_path),
                                'file_path': file_path,
                                'file_type': '.md',
                                'processed_at': datetime.now().isoformat()
                            }
                        }
                
                doc_processor = SimpleMarkdownProcessor(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
                logger.debug(f"✅ Using simple markdown processor for YouTube transcript (no docling needed)")
            except Exception as e:
                logger.error(f"❌ CRITICAL: Failed to initialize document processing components: {e}")
                logger.error(f"   Documents will NOT be saved to Neo4j/Elasticsearch.")
                # Continue without saving - we can still return the transcript
        
        # Let the tool function handle checking for existing documents and saving
        # Always pass components if available so tool can check cache and save new content
        result = summarize_youtube(
            url=url,
            language_codes=language_codes,
            save_to_documents=save_to_documents,  # Tool will handle caching logic
            user_id=user_id or "system",
            document_store=doc_store if (embedding_gen is not None and doc_processor is not None) else None,
            embedding_generator=embedding_gen,
            document_processor=doc_processor
        )
        
        return result
    
    registry.register_tool(LLMTool(
        name="summarize_youtube",
        description="CRITICAL: Use this tool EXACTLY as 'summarize_youtube' (not 'BMAD', not 'youtube', not anything else). Fetch YouTube video transcript and intelligently extract content. IMPORTANT: This tool ALWAYS fetches the transcript from YouTube (even if it's already saved) so you can summarize it. It checks if the transcript already exists in the document store, but still fetches and returns the transcript content for summarization. Automatically saves new transcripts to the document store for RAG queries. Use this when users ask about, summarize, or want information from a YouTube video URL. The tool can fetch transcripts from ANY YouTube video (if captions are available) and makes them searchable via RAG. Supports various YouTube URL formats (youtube.com/watch, youtu.be, etc.). Tool name is EXACTLY: summarize_youtube",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "YouTube video URL or video ID (e.g., 'https://www.youtube.com/watch?v=VIDEO_ID' or 'https://youtu.be/VIDEO_ID' or just 'VIDEO_ID')"
                },
                "language_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of language codes to try for transcript (default: ['en', 'en-US', 'en-GB']). Leave empty to auto-detect.",
                    "default": None
                },
                "save_to_documents": {
                    "type": "boolean",
                    "description": "Whether to save the transcript to the document store for RAG queries (default: true)",
                    "default": True
                },
                "force_refresh": {
                    "type": "boolean",
                    "description": "Force refresh even if transcript already exists (default: false)",
                    "default": False
                }
            },
            "required": ["url"]
        },
        function=summarize_youtube_wrapper
    ))
    
    # Tool: Generate image
    def generate_image_wrapper(
        prompt: str,
        negative_prompt: str = "bad hands, blurry, low quality, distorted",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg: float = 8.0,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Wrapper for image generation tool.
        Generates images using RunPod API with Stable Diffusion 1.5 + LoRA.
        """
        from src.tools.image_generation_tool import generate_image
        
        result = generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed
        )
        
        return result
    
    registry.register_tool(LLMTool(
        name="generate_image",
        description="Generate an image using AI image generation (Stable Diffusion 1.5 + LoRA). Use this tool when users ask to generate, create, make, or draw an image, picture, artwork, or visual content. IMPORTANT: This is the ONLY tool for image generation. DO NOT create dynamic tool names like 'create_dwarf_image' or 'generate_cat_image' - always use 'generate_image' and put the description in the 'prompt' parameter. Returns the path to the generated image file that can be sent to Discord.",
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed description of what to generate. Be specific about style, composition, colors, mood, and details."
                },
                "negative_prompt": {
                    "type": "string",
                    "description": "Things to avoid in the image (e.g., 'bad hands, blurry, low quality'). Default: 'bad hands, blurry, low quality, distorted'",
                    "default": "bad hands, blurry, low quality, distorted"
                },
                "width": {
                    "type": "integer",
                    "description": "Image width in pixels (default: 512)",
                    "default": 512
                },
                "height": {
                    "type": "integer",
                    "description": "Image height in pixels (default: 512)",
                    "default": 512
                },
                "steps": {
                    "type": "integer",
                    "description": "Number of sampling steps (default: 20, higher = better quality but slower)",
                    "default": 20
                },
                "cfg": {
                    "type": "number",
                    "description": "Classifier-free guidance scale (default: 8.0, higher = more adherence to prompt)",
                    "default": 8.0
                },
                "seed": {
                    "type": "integer",
                    "description": "Random seed for reproducibility (optional, leave null for random)"
                }
            },
            "required": ["prompt"]
        },
        function=generate_image_wrapper
    ))
    
    return registry

