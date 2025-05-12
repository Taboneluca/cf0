import os
from typing import Dict, Any, Optional
from .catalog import CATALOG, get_model_info
from .providers.openai_client import OpenAIClient
from .providers.anthropic_client import AnthropicClient
from .providers.groq_client import GroqClient
from .base import LLMClient

# Map provider names to client classes
_CLIENTS = {
   "openai": OpenAIClient,
   "anthropic": AnthropicClient,
   "groq": GroqClient,
}

# Cache for API keys
_API_KEYS = {}

def _get_api_key(provider: str) -> str:
    """Get API key for a provider, with caching"""
    if provider in _API_KEYS:
        return _API_KEYS[provider]
        
    # Get API key from environment
    env_var = f"{provider.upper()}_API_KEY"
    api_key = os.environ.get(env_var)
    
    if not api_key:
        raise ValueError(f"Missing API key for {provider}. Set {env_var} environment variable.")
        
    _API_KEYS[provider] = api_key
    return api_key

def get_client(model_key: str) -> LLMClient:
    """
    Get an LLM client instance for the specified model.
    
    Args:
        model_key: Model identifier (e.g., "openai:gpt-4o")
        
    Returns:
        An initialized LLM client for the model
        
    Raises:
        ValueError: If model_key is not in the catalog or provider is not supported
    """
    try:
        # Get model info from catalog
        model_info = get_model_info(model_key)
        provider = model_info["provider"]
        
        # Check if provider is supported
        if provider not in _CLIENTS:
            raise ValueError(f"Unsupported provider: {provider}")
            
        # Get API key for provider
        api_key = _get_api_key(provider)
        
        # Create client instance
        client_class = _CLIENTS[provider]
        return client_class(api_key=api_key, model=model_info["id"])
        
    except Exception as e:
        # Fall back to default model if specified model is not available
        fallback = os.environ.get("DEFAULT_MODEL", "openai:gpt-4o")
        if fallback != model_key:
            print(f"⚠️ Error creating client for {model_key}: {str(e)}. Falling back to {fallback}")
            return get_client(fallback)
        else:
            # If fallback is the same as requested model, propagate error
            raise ValueError(f"Failed to create client for {model_key}: {str(e)}")
            
def get_default_client() -> LLMClient:
    """Get the default LLM client from environment settings"""
    default_model = os.environ.get("DEFAULT_MODEL", "openai:gpt-4o")
    return get_client(default_model) 