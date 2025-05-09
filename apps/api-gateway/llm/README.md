# LLM Provider Abstraction

This module provides a consistent interface for interacting with various LLM providers.

## Supported Providers

| Provider | Environment Variable | Models |
|----------|---------------------|--------|
| OpenAI   | `OPENAI_API_KEY`    | `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-sonnet-20240229` (3.7 Sonnet), `claude-3.5-sonnet-202403` (3.5 Sonnet) |
| Groq     | `GROQ_API_KEY`      | `deepseek-r1-distil-llama-70b`, `llama-3.3-70b-versatile` |

## Usage

```python
from llm import PROVIDERS, SUPPORTED_MODELS

# Get a provider class by name
provider_key, model_id = "openai:gpt-4o-mini".split(":", 1)
LLMCls = PROVIDERS[provider_key]

# Instantiate with API key
llm_client = LLMCls(
    api_key=os.getenv(f"{provider_key.upper()}_API_KEY"),
    model=model_id
)

# Call the model
response = await llm_client.chat(
    messages=[
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Hello, world!"}
    ],
    stream=False,
    functions=functions_schema if llm_client.supports_function_call else None
)
```

## Adding New Providers

To add a new provider:

1. Create a new file in the `providers/` directory
2. Implement the `LLMClient` interface
3. Add it to the `PROVIDERS` dict in `__init__.py`
4. Add models to `SUPPORTED_MODELS` list in `__init__.py`
5. Add environment variable configuration to your deployment environment 