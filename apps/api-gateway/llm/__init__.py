from .providers.openai_client import OpenAIClient
from .providers.anthropic_client import AnthropicClient
from .providers.groq_client import GroqClient

PROVIDERS = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "groq": GroqClient,
}

# List of supported models
SUPPORTED_MODELS = [
    "openai:gpt-4o",                       # 4o (full context)
    "openai:gpt-4o-mini",                  # 4o-mini
    "openai:gpt-o3",                       # o3
    "openai:gpt-o4-mini",                  # o4-mini (keep as requested)
    "anthropic:claude-3-5-sonnet-latest",  # 3.5 sonnet
    "anthropic:claude-3-7-sonnet-latest",  # 3.7 sonnet
    "anthropic:claude-3-sonnet-20240229",  # Old Claude 3 Sonnet (for backward compatibility)
    "groq:llama-3.3-70b-versatile",        # Llama-3.3-70b-versatile
    "groq:llama-3.1-8b-instant",           # Llama-3.1-8b-instant
] 