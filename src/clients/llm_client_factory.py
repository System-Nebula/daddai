"""
Factory for creating LLM clients based on configuration.
Supports multiple OpenAI-compatible providers.
"""
import os
from typing import Optional
from config import (
    LLM_PROVIDER,
    LMSTUDIO_BASE_URL,
    LMSTUDIO_MODEL,
    LMSTUDIO_TIMEOUT,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    CHUTES_API_KEY,
    CHUTES_BASE_URL,
    CHUTES_MODEL,
    CHUTES_USE_INPUT_ARGS_WRAPPER,
    CUSTOM_LLM_BASE_URL,
    CUSTOM_LLM_API_KEY,
    CUSTOM_LLM_MODEL,
    LLM_STREAMING_ENABLED
)
from src.clients.openai_compatible_client import OpenAICompatibleClient
from logger_config import logger


def get_llm_client(
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
):
    """
    Factory function to get the appropriate LLM client.
    
    Args:
        provider: Provider name ("lmstudio", "openai", "chutes", "custom")
                 If None, uses LLM_PROVIDER from config
        base_url: Override base URL (optional)
        api_key: Override API key (optional)
        model: Override model name (optional)
    
    Returns:
        LLM client instance (OpenAICompatibleClient for all providers)
    """
    provider = (provider or LLM_PROVIDER).lower()
    
    if provider == "lmstudio":
        # Use OpenAICompatibleClient for LMStudio (supports tools and is OpenAI-compatible)
        # LMStudio uses the OpenAI API format, so we can use the same client
        client = OpenAICompatibleClient(
            base_url=base_url or LMSTUDIO_BASE_URL,
            api_key=None,  # LMStudio doesn't require API key
            model=model or LMSTUDIO_MODEL,
            timeout=LMSTUDIO_TIMEOUT
        )
        logger.info(f"Initialized LMStudio client: {client.base_url} (using OpenAICompatibleClient for tool support)")
        return client
    
    elif provider == "openai":
        if not api_key and not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set for OpenAI provider")
        
        client = OpenAICompatibleClient(
            base_url=base_url or OPENAI_BASE_URL,
            api_key=api_key or OPENAI_API_KEY,
            model=model or OPENAI_MODEL,
            timeout=LMSTUDIO_TIMEOUT
        )
        logger.info(f"Initialized OpenAI client: {client.base_url}")
        return client
    
    elif provider == "chutes":
        if not api_key and not CHUTES_API_KEY:
            raise ValueError("CHUTES_API_KEY must be set for Chutes provider")
        
        client = OpenAICompatibleClient(
            base_url=base_url or CHUTES_BASE_URL,
            api_key=api_key or CHUTES_API_KEY,
            model=model or CHUTES_MODEL,
            timeout=LMSTUDIO_TIMEOUT,
            use_input_args_wrapper=CHUTES_USE_INPUT_ARGS_WRAPPER
        )
        logger.info(f"Initialized Chutes AI client: {client.base_url} (input_args_wrapper={CHUTES_USE_INPUT_ARGS_WRAPPER})")
        return client
    
    elif provider == "custom":
        if not base_url and not CUSTOM_LLM_BASE_URL:
            raise ValueError("CUSTOM_LLM_BASE_URL must be set for custom provider")
        
        # Use longer timeout for GLM-4.6 thinking model (needs more time for reasoning)
        custom_timeout = int(os.getenv("CUSTOM_LLM_TIMEOUT", str(LMSTUDIO_TIMEOUT * 2)))  # Default to 60s for thinking models
        
        client = OpenAICompatibleClient(
            base_url=base_url or CUSTOM_LLM_BASE_URL,
            api_key=api_key or CUSTOM_LLM_API_KEY,
            model=model or CUSTOM_LLM_MODEL,
            timeout=custom_timeout
        )
        logger.info(f"Initialized custom LLM client: {client.base_url} (timeout: {custom_timeout}s)")
        return client
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Supported: lmstudio, openai, chutes, custom")


def get_default_llm_client():
    """Get the default LLM client based on configuration."""
    return get_llm_client()

