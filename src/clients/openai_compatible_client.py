"""
Generic OpenAI-compatible client for any provider that supports OpenAI API format.
Supports streaming, thinking models, and custom base URLs.
"""
import requests
import json
from typing import List, Dict, Any, Optional, Iterator, Callable, Union
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from logger_config import logger


class OpenAICompatibleClient:
    """Client for interacting with any OpenAI-compatible API provider."""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        use_input_args_wrapper: bool = False
    ):
        """
        Initialize OpenAI-compatible client.
        
        Args:
            base_url: Base URL for the API (e.g., "https://llm.chutes.ai/v1")
            api_key: API key/token (optional, some providers don't require it)
            model: Model name to use (can be overridden in generate calls)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            use_input_args_wrapper: If True, wrap request in {"input_args": {...}} format
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.use_input_args_wrapper = use_input_args_wrapper
        self.chat_endpoint = f"{self.base_url}/chat/completions"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authorization if API key is provided."""
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
        reraise=True
    )
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate a response using the OpenAI-compatible API (non-streaming).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model name to use (overrides instance model if provided)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response (for streaming, use generate_stream instead)
            tools: Optional list of tool definitions (OpenAI function calling format)
            tool_choice: Optional tool choice ("none", "auto", or {"type": "function", "function": {"name": "..."}})
            **kwargs: Additional parameters (top_p, top_k, etc.)
            
        Returns:
            Generated response text, or dict with 'content' and 'tool_calls' if tools were used
        """
        # For thinking models, use streaming by default to get actual responses
        # (non-streaming only returns reasoning, not the response)
        model_name = model or self.model
        is_thinking_model = model_name and 'thinking' in model_name.lower()
        if is_thinking_model and not stream:
            logger.debug(f"Detected thinking model {model_name}, using streaming to get actual response")
            stream = True
        
        if stream:
            # For streaming, collect all chunks
            # For thinking models, we need to filter out reasoning_content and only get actual content
            # CRITICAL: Read the ENTIRE stream until [DONE] - don't break early on finish_reason
            # Thinking models may send finish_reason before the actual content arrives
            full_response = ""
            tool_calls_accumulated = []
            thinking_seen = False
            finish_reason_seen = False
            content_received = False
            
            # Read the entire stream - don't break early
            # The stream will end naturally with [DONE] marker or connection close
            for chunk in self.generate_stream(
                messages, model, temperature, max_tokens,
                tools=tools, tool_choice=tool_choice, **kwargs
            ):
                # Skip reasoning_content chunks - only accumulate actual content
                # reasoning_content is the thinking process, not the response
                if chunk.get('reasoning_content'):
                    thinking_seen = True
                    logger.debug("Skipping reasoning_content chunk (thinking, not response)")
                    # Don't break - continue reading for actual content
                    continue
                
                # Only accumulate actual content (not thinking)
                if chunk.get('content') and not chunk.get('thinking'):
                    full_response += chunk['content']
                    content_received = True
                    logger.debug(f"Received content chunk: {len(chunk['content'])} chars (total: {len(full_response)})")
                elif chunk.get('content') and chunk.get('thinking'):
                    # If both are present, prefer content (actual response)
                    full_response += chunk['content']
                    content_received = True
                    logger.debug(f"Received content chunk (with thinking): {len(chunk['content'])} chars (total: {len(full_response)})")
                
                if chunk.get('tool_calls'):
                    tool_calls_accumulated.extend(chunk['tool_calls'])
                
                # Track finish_reason but NEVER break early - read the entire stream
                # For thinking models, content may come AFTER finish_reason
                if chunk.get('finish_reason'):
                    finish_reason_seen = True
                    logger.debug(f"Received finish_reason: {chunk.get('finish_reason')}, content_received: {content_received}, total_content: {len(full_response)}")
                    # Continue reading - don't break! The stream will end naturally with [DONE]
            
            # Log final state
            if thinking_seen:
                if content_received:
                    logger.info(f"Stream complete: received {len(full_response)} chars of content after thinking")
                else:
                    logger.warning("Received thinking chunks but no actual content chunks - thinking model may not have generated response yet")
            
            if tool_calls_accumulated:
                return {
                    "content": full_response,
                    "tool_calls": tool_calls_accumulated
                }
            return full_response
        
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        # Add tools if provided (OpenAI function calling format)
        if tools:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice
        
        # Add any additional parameters (top_p, top_k, presence_penalty, etc.)
        payload.update(kwargs)
        
        # Wrap in input_args if needed (for some Chutes endpoints)
        if self.use_input_args_wrapper:
            payload = {"input_args": payload}
        
        try:
            model_name = model or self.model
            
            # Calculate payload size for debugging
            payload_json = json.dumps(payload)
            payload_size_bytes = len(payload_json.encode('utf-8'))
            payload_size_kb = payload_size_bytes / 1024
            
            # Count tools if present
            tool_count = 0
            if tools:
                tool_count = len(tools)
            
            # Calculate system message size if present
            system_msg_size = 0
            if messages and len(messages) > 0:
                first_msg = messages[0]
                if first_msg.get('role') == 'system':
                    system_msg_size = len(first_msg.get('content', ''))
            
            logger.info(f"📤 API Request: {self.base_url}")
            logger.info(f"   Model: {model_name}")
            logger.info(f"   Messages: {len(messages)}")
            logger.info(f"   Tools: {tool_count}")
            logger.info(f"   Payload size: {payload_size_kb:.2f} KB ({payload_size_bytes:,} bytes)")
            logger.info(f"   System message size: {system_msg_size:,} chars")
            logger.info(f"   Timeout: {self.timeout}s")
            logger.debug(f"Payload keys: {list(payload.keys())}, use_input_args_wrapper={self.use_input_args_wrapper}")
            
            import time
            request_start = time.time()
            
            try:
                response = requests.post(
                    self.chat_endpoint,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout
                )
                
                request_elapsed = time.time() - request_start
                logger.info(f"📥 API Response received in {request_elapsed:.2f}s (status: {response.status_code})")
            except requests.exceptions.Timeout:
                request_elapsed = time.time() - request_start
                logger.error(f"⏱️  API Request TIMEOUT after {request_elapsed:.2f}s (timeout was {self.timeout}s)")
                logger.error(f"   This indicates the API is hanging or taking too long to respond")
                logger.error(f"   Payload size: {payload_size_kb:.2f} KB, Tools: {tool_count}, System msg: {system_msg_size:,} chars")
                raise
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"API error ({response.status_code}): {error_detail}")
                logger.error(f"Request details: endpoint={self.chat_endpoint}, model={model_name}, payload_keys={list(payload.keys())}")
                # For 404 errors, provide more helpful message
                if response.status_code == 404:
                    logger.error(f"Model '{model_name}' may not be available on Chutes. Check:")
                    logger.error(f"  1. Model name is correct: {model_name}")
                    logger.error(f"  2. Model is configured in your Chutes account")
                    logger.error(f"  3. API key has access to this model")
                raise Exception(f"API error ({response.status_code}): {error_detail}")
            
            response.raise_for_status()
            result = response.json()
            
            # Log API response for debugging
            logger.info(f"📥 API Response details:")
            logger.info(f"   Response keys: {list(result.keys())}")
            if 'choices' in result:
                logger.info(f"   Choices count: {len(result['choices'])}")
                if len(result['choices']) > 0:
                    choice = result['choices'][0]
                    logger.info(f"   Finish reason: {choice.get('finish_reason', 'unknown')}")
                    msg = choice.get('message', {})
                    logger.info(f"   Message keys: {list(msg.keys())}")
                    logger.info(f"   Content length: {len(msg.get('content', '')) if msg.get('content') else 0} chars")
                    if msg.get('content'):
                        logger.info(f"   Content preview: {msg.get('content', '')[:200]}...")
                    if msg.get('tool_calls'):
                        logger.info(f"   Tool calls: {len(msg.get('tool_calls', []))}")
            if 'usage' in result:
                usage = result['usage']
                logger.info(f"   Tokens - prompt: {usage.get('prompt_tokens', 0)}, completion: {usage.get('completion_tokens', 0)}, total: {usage.get('total_tokens', 0)}")
            
            if 'choices' not in result or len(result['choices']) == 0:
                logger.error(f"Unexpected response format: {result}")
                raise Exception(f"Unexpected response format: {result}")
            
            choice = result['choices'][0]
            message = choice.get('message', {})
            content = message.get('content')
            finish_reason = choice.get('finish_reason')
            
            # Handle None or empty content (common with thinking models)
            # For thinking models, content might be null or empty because we need to use streaming
            # to get the actual response (thinking comes first, then response)
            # Also handle when finish_reason is "length" - means we hit token limit
            if content is None or (isinstance(content, str) and len(content.strip()) == 0):
                reasoning_content = message.get('reasoning_content')
                logger.warning(f"Received empty content from API (thinking model). Finish reason: {finish_reason}, Has reasoning_content: {bool(reasoning_content)}")
                if finish_reason == "length":
                    logger.warning(f"⚠️ Hit token limit (finish_reason=length). Completion tokens: {result.get('usage', {}).get('completion_tokens', 0)}")
                    logger.warning(f"   Consider increasing max_tokens (current: {max_tokens})")
                logger.warning(f"Full response structure: {json.dumps(result, indent=2)[:1000]}")
                
                # For thinking models, we need to use streaming to get the actual response
                # The non-streaming response only contains reasoning, not the actual output
                # Also retry with higher max_tokens if we hit length limit
                if finish_reason == "length":
                    logger.info(f"Retrying with streaming and increased max_tokens ({max_tokens * 2}) to get actual response")
                    retry_max_tokens = max_tokens * 2
                else:
                    logger.info(f"Retrying with streaming to get actual response from thinking model")
                    retry_max_tokens = max_tokens
                try:
                    # Use streaming to get the actual response
                    # CRITICAL: Read the ENTIRE stream - don't break early
                    full_content = ""
                    content_received = False
                    for chunk in self.generate_stream(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=retry_max_tokens,
                        tools=tools,
                        tool_choice=tool_choice,
                        **kwargs
                    ):
                        # Skip reasoning_content - only accumulate actual content
                        if chunk.get('reasoning_content'):
                            logger.debug("Skipping reasoning_content in streaming retry")
                            continue
                        
                        if chunk.get('content') and not chunk.get('thinking'):
                            full_content += chunk['content']
                            content_received = True
                            logger.debug(f"Received content in retry: {len(chunk['content'])} chars (total: {len(full_content)})")
                        
                        # NEVER break early - read the entire stream until [DONE]
                        # Content may come after finish_reason for thinking models
                    
                    if full_content:
                        logger.info(f"Got response from streaming: {len(full_content)} characters")
                        return full_content
                    else:
                        logger.warning(f"Streaming also returned empty content")
                        # Last resort: if we have reasoning_content but no content, try to extract JSON from reasoning
                        # Sometimes GLM-4.6 puts the JSON in reasoning_content when hitting token limits
                        if reasoning_content:
                            import re
                            # Try to extract JSON from reasoning_content
                            json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', reasoning_content)
                            if json_match:
                                logger.info(f"Extracted JSON from reasoning_content as fallback")
                                content = json_match.group(0)
                            else:
                                content = ''
                        else:
                            content = ''
                except Exception as stream_error:
                    logger.warning(f"Streaming retry failed: {stream_error}")
                    content = ''
            elif not isinstance(content, str):
                # Content might be in a different format
                logger.warning(f"Content is not a string: {type(content)}. Value: {content}")
                content = str(content) if content else ''
            
            # Check for tool calls (function calling)
            tool_calls = message.get('tool_calls')
            if tool_calls:
                logger.debug(f"Received {len(tool_calls)} tool calls from API")
                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "finish_reason": choice.get('finish_reason')
                }
            
            # Log if content is empty but we got a response
            if not content:
                logger.warning(f"Empty content in response. Choice: {json.dumps(choice, indent=2)[:500]}")
                logger.warning(f"Full result keys: {list(result.keys())}")
            
            logger.debug(f"Generated response: {len(content) if content else 0} characters")
            return content
        except requests.exceptions.Timeout:
            logger.error(f"API timeout after {self.timeout}s")
            raise Exception(f"API timeout after {self.timeout}s")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling API: {e}")
            raise Exception(f"Error calling API: {e}")
    
    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        on_chunk: Optional[Callable[[Dict[str, Any]], None]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **kwargs
    ) -> Iterator[Dict[str, Any]]:
        """
        Generate a streaming response using the OpenAI-compatible API.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model name to use (overrides instance model if provided)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            on_chunk: Optional callback function called for each chunk
            tools: Optional list of tool definitions (OpenAI function calling format)
            tool_choice: Optional tool choice ("none", "auto", or {"type": "function", "function": {"name": "..."}})
            **kwargs: Additional parameters
            
        Yields:
            Dictionary with chunk data:
            - content: str (text content, may be empty for some chunks)
            - delta: dict (raw delta from API)
            - finish_reason: str (if chunk indicates completion)
            - thinking: str (for thinking models, if present)
            - tool_calls: list (if tool calls are present in chunk)
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        # Add tools if provided (OpenAI function calling format)
        if tools:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice
        
        # Add any additional parameters (top_p, top_k, presence_penalty, etc.)
        payload.update(kwargs)
        
        # Wrap in input_args if needed (for some Chutes endpoints)
        if self.use_input_args_wrapper:
            payload = {"input_args": payload}
        
        try:
            model_name = model or self.model
            logger.debug(f"Starting streaming request to {self.base_url} with {len(messages)} messages, model={model_name}")
            logger.debug(f"Payload keys: {list(payload.keys())}, use_input_args_wrapper={self.use_input_args_wrapper}")
            
            response = requests.post(
                self.chat_endpoint,
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"API error ({response.status_code}): {error_detail}")
                logger.error(f"Request details: endpoint={self.chat_endpoint}, model={model_name}, payload_keys={list(payload.keys())}")
                # For 404 errors, provide more helpful message
                if response.status_code == 404:
                    logger.error(f"Model '{model_name}' may not be available on Chutes. Check:")
                    logger.error(f"  1. Model name is correct: {model_name}")
                    logger.error(f"  2. Model is configured in your Chutes account")
                    logger.error(f"  3. API key has access to this model")
                raise Exception(f"API error ({response.status_code}): {error_detail}")
            
            response.raise_for_status()
            
            # Process Server-Sent Events (SSE) stream
            buffer = ""
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                
                # SSE format: "data: {...}"
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    
                    # Handle [DONE] marker
                    if data_str.strip() == "[DONE]":
                        break
                    
                    try:
                        chunk_data = json.loads(data_str)
                        
                        # Extract content from chunk
                        chunk = {
                            "content": "",
                            "delta": {},
                            "finish_reason": None,
                            "thinking": None
                        }
                        
                        if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                            choice = chunk_data['choices'][0]
                            
                            # Extract delta (content increment)
                            if 'delta' in choice:
                                delta = choice['delta']
                                chunk['delta'] = delta
                                
                                # Get content from delta
                                if 'content' in delta and delta['content']:
                                    chunk['content'] = delta['content']
                                
                                # Chutes thinking models use 'reasoning_content' in delta
                                # This is the thinking process, NOT the actual response
                                # We should NOT use it as content - the actual response comes later in the stream
                                if 'reasoning_content' in delta and delta['reasoning_content']:
                                    chunk['reasoning_content'] = delta['reasoning_content']
                                    # Do NOT use reasoning_content as content - it's thinking, not response
                                    logger.debug("Received reasoning_content in stream (thinking process, not response)")
                                
                                # Check for thinking content (for thinking models)
                                # This is also thinking, not the actual response
                                if 'thinking' in delta and delta['thinking']:
                                    chunk['thinking'] = delta['thinking']
                                    # Do NOT use thinking as content - it's the thinking process
                                    logger.debug("Received thinking in stream (thinking process, not response)")
                            
                            # Check for tool calls in delta (function calling)
                            # Tool calls can be in delta or at choice level
                            if 'tool_calls' in delta:
                                chunk['tool_calls'] = delta['tool_calls']
                            elif 'tool_calls' in choice:
                                chunk['tool_calls'] = choice['tool_calls']
                            
                            # Get finish reason (Chutes uses both finish_reason and stop_reason)
                            if 'finish_reason' in choice:
                                chunk['finish_reason'] = choice['finish_reason']
                            elif 'stop_reason' in choice:
                                # Chutes API may use stop_reason instead
                                chunk['finish_reason'] = choice['stop_reason']
                            
                            # Also capture stop_reason if present (for Chutes compatibility)
                            if 'stop_reason' in choice:
                                chunk['stop_reason'] = choice['stop_reason']
                        
                        # Call callback if provided
                        if on_chunk:
                            on_chunk(chunk)
                        
                        yield chunk
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse chunk: {data_str[:100]}... Error: {e}")
                        continue
                elif line.startswith(":"):
                    # SSE comment line, ignore
                    continue
                else:
                    # Accumulate in buffer for multi-line chunks
                    buffer += line + "\n"
            
            logger.debug("Streaming completed")
            
        except requests.exceptions.Timeout:
            logger.error(f"API timeout after {self.timeout}s")
            raise Exception(f"API timeout after {self.timeout}s")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling API: {e}")
            raise Exception(f"Error calling API: {e}")
    
    def check_connection(self) -> bool:
        """Check if the API is accessible."""
        try:
            # Try a simple request to models endpoint if available
            models_url = f"{self.base_url}/models"
            response = requests.get(models_url, headers=self._get_headers(), timeout=5)
            return response.status_code == 200
        except:
            # If models endpoint doesn't exist, try a minimal chat request
            try:
                test_payload = {
                    "model": self.model or "test",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1
                }
                response = requests.post(
                    self.chat_endpoint,
                    json=test_payload,
                    headers=self._get_headers(),
                    timeout=5
                )
                # Accept 200 (success) or 400 (bad request but API is reachable)
                return response.status_code in [200, 400]
            except:
                return False
    
    def get_available_models(self) -> List[str]:
        """Get list of available models from the API."""
        try:
            models_url = f"{self.base_url}/models"
            response = requests.get(models_url, headers=self._get_headers(), timeout=5)
            response.raise_for_status()
            models = response.json()
            return [model['id'] for model in models.get('data', [])]
        except:
            return []

