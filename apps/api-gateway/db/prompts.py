"""
Prompt persistence helpers (Phase-5)

All functions are synchronous because the official Supabase
Python client is sync. Feel free to wrap in `asyncio.to_thread`
if you move to async Postgres later.
"""
from __future__ import annotations
import time
from typing import Dict, Tuple, List
from .supa import supabase  # ⇐ already initialised elsewhere

# -------------------------------------------------------------------
# Local LRU + TTL (60 s) cache --------------------------------------
# -------------------------------------------------------------------
_TTL_SECONDS = 60
_CACHE: Dict[str, Tuple[str, float]] = {}        # mode -> (prompt_text, epoch)

def _cache_get(mode: str) -> str | None:
    entry = _CACHE.get(mode)
    if not entry:
        return None
    text, ts = entry
    if time.time() - ts > _TTL_SECONDS:
        _CACHE.pop(mode, None)                    # expire
        return None
    return text

def _cache_put(mode: str, text: str) -> None:
    # Simple LRU eviction (32 entries max)
    if len(_CACHE) >= 32:
        # pop the oldest
        oldest = min(_CACHE.items(), key=lambda kv: kv[1][1])[0]
        _CACHE.pop(oldest, None)
    _CACHE[mode] = (text, time.time())

# -------------------------------------------------------------------
# DB helpers ---------------------------------------------------------
# -------------------------------------------------------------------
def _fetch_active_prompt(mode: str) -> str:
    """Return active prompt text for an agent mode, raise if missing."""
    if supabase is None:
        raise RuntimeError("Supabase client not configured")
    res = (
        supabase.table("prompts")
        .select("text")
        .eq("agent_mode", mode)
        .eq("is_active", True)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]["text"]
    raise ValueError(f"No active prompt found for mode '{mode}'")

def get_active_prompt(mode: str) -> str:
    """60 s TTL look-up used by BaseAgent."""
    cached = _cache_get(mode)
    if cached is not None:
        return cached
    text = _fetch_active_prompt(mode)
    _cache_put(mode, text)
    return text

def list_prompts(mode: str) -> List[dict]:
    """Return **all** stored versions for admin UI (latest first)."""
    res = (
        supabase.table("prompts")
        .select("*")
        .eq("agent_mode", mode)
        .order("version", desc=True)
        .execute()
    )
    return res.data or []

def create_prompt(mode: str, text: str, created_by: str) -> dict:
    """
    Insert new prompt version and make it active.
    Previous active version is automatically de-activated.
    """
    # find next version number
    latest = (
        supabase.table("prompts")
        .select("version")
        .eq("agent_mode", mode)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    next_version = (latest.data[0]["version"] + 1) if latest.data else 1

    # deactivate older active prompt
    supabase.table("prompts") \
        .update({"is_active": False}) \
        .eq("agent_mode", mode) \
        .eq("is_active", True) \
        .execute()

    result = supabase.table("prompts").insert({
        "agent_mode": mode,
        "text": text,
        "version": next_version,
        "is_active": True,
        "created_by": created_by,
    }).execute()

    # bust cache
    _CACHE.pop(mode, None)
    return result.data[0] 