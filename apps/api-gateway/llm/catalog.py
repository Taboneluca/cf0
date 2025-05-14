import os
from typing import Dict, List, Any

# Central model catalog - can be expanded without changing code
CATALOG: Dict[str, Dict[str, Any]] = {
    # key                      provider     model id on provider          supports_tools  display_name
    "openai:gpt-4o":          {"provider": "openai",    "id": "gpt-4o",                "tool_calls": True, "label": "gpt-4o"},
    "openai:gpt-4o-mini":     {"provider": "openai",    "id": "gpt-4o-mini",           "tool_calls": True, "label": "gpt-4o-mini"},
    "openai:gpt-o3":          {"provider": "openai",    "id": "gpt-3.5-turbo",         "tool_calls": True, "label": "gpt-o3"},  # name alias
    "openai:gpt-o4-mini":     {"provider": "openai",    "id": "gpt-4-turbo",           "tool_calls": True, "label": "gpt-o4-mini"},  # name alias
    "anthropic:claude-3-5-sonnet": {"provider": "anthropic", "id": "claude-3-sonnet-20240229", "tool_calls": True, "label": "claude-3.5-Sonnet"},
    "anthropic:claude-3-7-sonnet": {"provider": "anthropic", "id": "claude-3-sonnet-20240229", "tool_calls": True, "label": "claude-3.7-Sonnet"},
    "groq:llama-3-3-70b":     {"provider": "groq",      "id": "llama3-70b-8192", "tool_calls": True, "label": "Llama-3.3-70B"},
    "groq:llama-3-1-8b":      {"provider": "groq",      "id": "llama-3.1-8b-instant",    "tool_calls": True, "label": "Llama-3.1-8B"},
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
                    "tool_calls": tool_calls.lower() == "true",
                    "label": model_id.replace("-", " ").title()  # Default label
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
            "label": info.get("label", key.split(":", 1)[1].replace("-", " ").title()),  # Use defined label or fallback
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