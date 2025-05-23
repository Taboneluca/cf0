from .providers.openai_client import OpenAIClient
from .providers.anthropic_client import AnthropicClient
from .providers.groq_client import GroqClient
from .streaming_utils import StreamGuard, wrap_stream_with_guard

PROVIDERS = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "groq": GroqClient,
}

# List of supported models
SUPPORTED_MODELS = [
    "openai:gpt-4o",                 # 4o (full context)
    "openai:gpt-4o-mini",            # 4o-mini
    "openai:gpt-o3",                 # o3
    "openai:gpt-o4-mini",            # o4-mini
    "anthropic:claude-3-5-sonnet",   # 3.5 sonnet
    "anthropic:claude-3-7-sonnet",   # 3.7 sonnet
    "groq:llama-3-3-70b",            # Llama-3.3-70b-versatile
    "groq:llama-3-8b",               # Llama-3-8b
]

# Make the streaming utilities available at the package level
__all__ = ["OpenAIClient", "AnthropicClient", "GroqClient", "PROVIDERS", "SUPPORTED_MODELS", "StreamGuard", "wrap_stream_with_guard"] 