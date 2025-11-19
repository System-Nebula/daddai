"""
LMStudio client for querying local LLM models with retry logic.
Now also supports streaming via OpenAICompatibleClient.
"""
import httpx
from typing import List, Dict, Any, Optional, Iterator
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import (
    LMSTUDIO_BASE_URL, LMSTUDIO_MODEL, LMSTUDIO_TIMEOUT, LMSTUDIO_MAX_RETRIES,
    LLM_STREAMING_ENABLED
)
from logger_config import logger


class LMStudioClient:
    """Client for interacting with LMStudio API."""
    
    def __init__(self, base_url: str = LMSTUDIO_BASE_URL, model: str = None):
        """
        Initialize LMStudio client.
        
        Args:
            base_url: Base URL for LMStudio API (default: http://localhost:1234/v1)
            model: Model name to use (None for auto-detect)
        """
        self.base_url = base_url.rstrip('/')
        
        import sys
        
        # Auto-detect model if not specified
        if model is None:
            available_models = self.get_available_models()
            if available_models:
                # Prefer instruct/chat models, otherwise use first available
                instruct_models = [m for m in available_models if 'instruct' in m.lower() or 'chat' in m.lower()]
                self.model = instruct_models[0] if instruct_models else available_models[0]
                print(f"Auto-detected LMStudio model: {self.model}", file=sys.stderr)
            else:
                self.model = LMSTUDIO_MODEL
                print(f"Using default model: {self.model}", file=sys.stderr)
        else:
            self.model = model
        
        self.chat_endpoint = f"{self.base_url}/chat/completions"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=True
    )
    def generate_response(self, 
                         messages: List[Dict[str, str]], 
                         temperature: float = 0.7,
                         max_tokens: int = 1000,
                         stream: bool = False) -> str:
        """
        Generate a response using LMStudio with retry logic.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response (for streaming, use generate_stream instead)
            
        Returns:
            Generated response text
        """
        if stream and LLM_STREAMING_ENABLED:
            # For streaming, collect all chunks
            full_response = ""
            for chunk in self.generate_stream(messages, temperature, max_tokens):
                if chunk.get('content'):
                    full_response += chunk['content']
            return full_response
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            logger.debug(f"Calling LMStudio API with {len(messages)} messages")
            with httpx.Client(timeout=LMSTUDIO_TIMEOUT) as client:
                response = client.post(
                    self.chat_endpoint,
                    json=payload
                )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"LMStudio API error ({response.status_code}): {error_detail}")
                raise Exception(f"LMStudio API error ({response.status_code}): {error_detail}")
            
            response.raise_for_status()
            result = response.json()
            
            if 'choices' not in result or len(result['choices']) == 0:
                logger.error(f"Unexpected response format: {result}")
                raise Exception(f"Unexpected response format: {result}")
            
            content = result['choices'][0]['message']['content']
            logger.debug(f"Generated response: {len(content)} characters")
            return content
        except httpx.TimeoutException:
            logger.error(f"LMStudio API timeout after {LMSTUDIO_TIMEOUT}s")
            raise Exception(f"LMStudio API timeout after {LMSTUDIO_TIMEOUT}s")
        except httpx.RequestError as e:
            logger.error(f"Error calling LMStudio API: {e}")
            raise Exception(f"Error calling LMStudio API: {e}")
    
    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Iterator[Dict[str, Any]]:
        """
        Generate a streaming response using LMStudio API.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Yields:
            Dictionary with chunk data (same format as OpenAICompatibleClient)
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        try:
            logger.debug(f"Starting streaming request to LMStudio with {len(messages)} messages")
            with httpx.Client(timeout=LMSTUDIO_TIMEOUT) as client:
                with client.stream('POST', self.chat_endpoint, json=payload) as response:
                    if response.status_code != 200:
                        error_detail = response.text
                        logger.error(f"LMStudio API error ({response.status_code}): {error_detail}")
                        raise Exception(f"LMStudio API error ({response.status_code}): {error_detail}")
                    
                    response.raise_for_status()
                    
                    # Process Server-Sent Events (SSE) stream
                    import json
                    buffer = ""
                    for line in response.iter_lines():
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
                                        if 'content' in delta:
                                            chunk['content'] = delta['content']
                                        
                                        # Check for thinking content (for thinking models)
                                        if 'thinking' in delta:
                                            chunk['thinking'] = delta['thinking']
                                    
                                    # Get finish reason
                                    if 'finish_reason' in choice:
                                        chunk['finish_reason'] = choice['finish_reason']
                                
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
            
        except httpx.TimeoutException:
            logger.error(f"LMStudio API timeout after {LMSTUDIO_TIMEOUT}s")
            raise Exception(f"LMStudio API timeout after {LMSTUDIO_TIMEOUT}s")
        except httpx.RequestError as e:
            logger.error(f"Error calling LMStudio API: {e}")
            raise Exception(f"Error calling LMStudio API: {e}")
    
    def check_connection(self) -> bool:
        """Check if LMStudio is accessible."""
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/models")
                return response.status_code == 200
        except:
            return False
    
    def get_available_models(self) -> List[str]:
        """Get list of available models from LMStudio."""
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.base_url}/models")
                response.raise_for_status()
                models = response.json()
                return [model['id'] for model in models.get('data', [])]
        except:
            return []
