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
    "openai:gpt-4o-mini",
    "anthropic:claude-3-sonnet-20240229",  # 3.7 Sonnet
    "anthropic:claude-3.5-sonnet-202403",  # 3.5 Sonnet
    "groq:deepseek-r1-distil-llama-70b",   # DeepSeek R1 Distil Llama 70B
    "groq:llama-3.3-70b-versatile",        # Llama-3.3-70b-versatile
] 