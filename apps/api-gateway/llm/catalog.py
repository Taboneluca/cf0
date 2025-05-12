import os
from typing import Dict, List, Any

# Central model catalog - can be expanded without changing code
CATALOG: Dict[str, Dict[str, Any]] = {
    # key                      provider     model id on provider          supports_tools  
    "openai:gpt-4o":          {"provider": "openai",    "id": "gpt-4o",                "tool_calls": True},
    "openai:gpt-4o-mini":     {"provider": "openai",    "id": "gpt-4o-mini",           "tool_calls": True},
    "openai:gpt-o3":          {"provider": "openai",    "id": "gpt-3.5-turbo",         "tool_calls": True},  # name alias
    "openai:gpt-o4-mini":     {"provider": "openai",    "id": "gpt-4-turbo",           "tool_calls": True},  # name alias
    "anthropic:claude-3-5-sonnet": {"provider": "anthropic", "id": "claude-3-5-sonnet-20240620", "tool_calls": True},
    "anthropic:claude-3-7-sonnet": {"provider": "anthropic", "id": "claude-3-7-sonnet-20240620", "tool_calls": True},
    "groq:llama-3-3-70b":     {"provider": "groq",      "id": "llama-3.1-70b-versatile", "tool_calls": True},
    "groq:llama-3-1-8b":      {"provider": "groq",      "id": "llama-3.1-8b-instant",    "tool_calls": True},
}

# Load additional models from environment variables (format: MODEL_KEY_1=provider:id:tool_calls)
def _load_env_models():
    for k, v in os.environ.items():
        if k.startswith("MODEL_"):
            try:
                provider, model_id, tool_calls = v.split(":", 2)
                model_key = f"{provider}:{model_id}"
                CATALOG[model_key] = {
                    "provider": provider,
                    "id": model_id,
                    "tool_calls": tool_calls.lower() == "true"
                }
            except Exception as e:
                print(f"Error loading model from env var {k}: {e}")

# Call on startup
_load_env_models()

def get_models() -> List[Dict[str, Any]]:
    """Return all available models in a format suitable for the frontend"""
    return [
        {
            "value": key,
            "label": key.split(":", 1)[1].replace("-", " ").title(),  # Format for UI
            "provider": info["provider"],
            "tool_calls": info["tool_calls"]
        }
        for key, info in CATALOG.items()
    ]

def get_model_info(model_key: str) -> Dict[str, Any]:
    """Get information about a specific model"""
    if model_key not in CATALOG:
        raise ValueError(f"Unknown model: {model_key}")
    return CATALOG[model_key] 