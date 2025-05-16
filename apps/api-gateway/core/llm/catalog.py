import os
from typing import Dict, List, Any

# Central model catalog - can be expanded without changing code
CATALOG: Dict[str, Dict[str, Any]] = {
    # key                      provider     model id on provider      supports_tools  max_tokens  display_name
    "openai:gpt-4o":          {"provider": "openai",    "id": "gpt-4o",              "tool_calls": True, "max_tokens": 128000, "label": "4o"},
    "openai:gpt-4o-mini":     {"provider": "openai",    "id": "gpt-4o-mini",         "tool_calls": True, "max_tokens": 128000, "label": "4o-mini"},
    "openai:gpt-o3":          {"provider": "openai",    "id": "o3",                  "tool_calls": True, "max_tokens": 128000, "label": "o3"},  
    "openai:gpt-o4-mini":     {"provider": "openai",    "id": "o4-mini",             "tool_calls": True, "max_tokens": 128000, "label": "o4-mini"},  
    "anthropic:claude-3-5-sonnet": {"provider": "anthropic", "id": "claude-3-5-sonnet-20240620", "tool_calls": True, "max_tokens": 200000, "label": "Claude 3.5 sonnet"},
    "anthropic:claude-3-7-sonnet": {"provider": "anthropic", "id": "claude-3-7-sonnet-20250219", "tool_calls": True, "max_tokens": 200000, "label": "Claude 3.7 sonnet"},
    "groq:llama-3-3-70b":     {"provider": "groq",      "id": "llama-3.3-70b-versatile", "tool_calls": True, "max_tokens": 32768, "label": "Llama-3.3-70B"},
    "groq:llama-3-8b":        {"provider": "groq",      "id": "llama3-8b-8192",    "tool_calls": True, "max_tokens": 8192, "label": "Llama-3-8B"},
}

# Load additional models from environment variables (format: MODEL_KEY_1=provider:id:tool_calls:max_tokens)
def _load_env_models():
    for k, v in os.environ.items():
        if k.startswith("MODEL_"):
            try:
                parts = v.split(":", 3)
                if len(parts) >= 3:
                    provider, model_id, tool_calls = parts[:3]
                    max_tokens = int(parts[3]) if len(parts) > 3 else 4096  # Default to 4096 if not specified
                    
                    model_key = f"{provider}:{model_id}"
                    CATALOG[model_key] = {
                        "provider": provider,
                        "id": model_id,
                        "tool_calls": tool_calls.lower() == "true",
                        "max_tokens": max_tokens,
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
            "tool_calls": info["tool_calls"],
            "max_tokens": info["max_tokens"]
        }
        for key, info in CATALOG.items()
    ]

def get_model_info(model_key: str) -> Dict[str, Any]:
    """Get information about a specific model"""
    if model_key not in CATALOG:
        raise ValueError(f"Unknown model: {model_key}")
    return CATALOG[model_key] 