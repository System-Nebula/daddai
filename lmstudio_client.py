"""
LMStudio client for querying local LLM models with retry logic.
"""
import requests
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import LMSTUDIO_BASE_URL, LMSTUDIO_MODEL, LMSTUDIO_TIMEOUT, LMSTUDIO_MAX_RETRIES
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
        retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
        reraise=True
    )
    def generate_response(self, 
                         messages: List[Dict[str, str]], 
                         temperature: float = 0.7,
                         max_tokens: int = 1000) -> str:
        """
        Generate a response using LMStudio with retry logic.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated response text
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            logger.debug(f"Calling LMStudio API with {len(messages)} messages")
            response = requests.post(
                self.chat_endpoint,
                json=payload,
                timeout=LMSTUDIO_TIMEOUT
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
        except requests.exceptions.Timeout:
            logger.error(f"LMStudio API timeout after {LMSTUDIO_TIMEOUT}s")
            raise Exception(f"LMStudio API timeout after {LMSTUDIO_TIMEOUT}s")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling LMStudio API: {e}")
            raise Exception(f"Error calling LMStudio API: {e}")
    
    def check_connection(self) -> bool:
        """Check if LMStudio is accessible."""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_available_models(self) -> List[str]:
        """Get list of available models from LMStudio."""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            response.raise_for_status()
            models = response.json()
            return [model['id'] for model in models.get('data', [])]
        except:
            return []
