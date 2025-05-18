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

# Map from provider-qualified model names to internal model IDs
ALIAS_MAP = {
    # Groq aliases
    "groq:llama-3-3-70b":          "llama-3.3-70b-versatile",
    "groq:llama-3.3-70b-versatile": "llama-3.3-70b-versatile",
    "llama-3.3-70b-versatile":      "llama-3.3-70b-versatile",
    "llama-3-3-70b":               "llama-3.3-70b-versatile",
    "groq:llama3-8b-8192":         "llama3-8b-8192",
    "llama3-8b-8192":              "llama3-8b-8192",
    "groq:llama-3-8b":             "llama3-8b-8192",
    "llama-3-8b":                  "llama3-8b-8192",
    "groq:llama3-70b-8192":        "llama3-70b-8192",
    "llama3-70b-8192":             "llama3-70b-8192",
    
    # Anthropic aliases
    "anthropic:claude-3-7-sonnet": "claude-3-7-sonnet-20250219",
    "claude-3-7-sonnet":           "claude-3-7-sonnet-20250219",
    "anthropic:claude-3-5-sonnet": "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet":           "claude-3-5-sonnet-20240620",
    
    # OpenAI aliases
    "openai:gpt-4o":              "gpt-4o",
    "gpt-4o":                     "gpt-4o",
    "openai:gpt-4o-mini":         "gpt-4o-mini",
    "gpt-4o-mini":                "gpt-4o-mini",
    "openai:gpt-o3":              "o3",
    "gpt-o3":                     "o3",
    "openai:gpt-o4-mini":         "o4-mini",
    "gpt-o4-mini":                "o4-mini",
}

def normalize_model_name(model: str) -> str:
    """
    Normalize a model name by handling provider prefixes and alias mapping.
    
    Args:
        model: Raw model name, possibly with provider prefix (e.g., "groq:llama-3-8b")
        
    Returns:
        Normalized model ID suitable for provider APIs
    """
    # First try direct lookup in the alias map
    if model in ALIAS_MAP:
        return ALIAS_MAP[model]
        
    # For provider-prefixed models, strip the prefix and check again
    if ":" in model:
        provider, model_id = model.split(":", 1)
        # Try with just the model_id
        if model_id in ALIAS_MAP:
            return ALIAS_MAP[model_id]
    
    # Return as-is if no mapping exists
    return model

def normalise(model: str) -> str:
    """Convert provider-qualified model names to internal IDs for token counting"""
    return normalize_model_name(model)

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