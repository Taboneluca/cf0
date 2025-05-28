"""
New prompt system - prefers JSON files, falls back to Supabase for overrides
Implements P-T-C-F (Persona-Task-Context-Format) structure
"""
from __future__ import annotations
import json
import time
from pathlib import Path, PurePath
from typing import Dict, Any, List
from functools import lru_cache

from db.supa import prompts_supabase

# -------------------------------------------------------------------
# JSON-based prompt loading
# -------------------------------------------------------------------

@lru_cache(maxsize=16)
def load_prompt_spec(mode: str) -> Dict[str, Any]:
    """
    Load prompt specification, preferring repo JSON over Supabase override.
    
    Args:
        mode: 'ask' or 'analyst'
        
    Returns:
        Prompt specification dictionary
    """
    # First try loading from JSON file in repo
    prompt_path = Path("docs/prompts") / f"{mode}_v2.0.json"
    
    try:
        with open(prompt_path, 'r') as f:
            spec = json.load(f)
            print(f"✅ Loaded {mode} prompt from {prompt_path}")
            return spec
    except FileNotFoundError:
        print(f"⚠️  No JSON file found at {prompt_path}, falling back to database")
    except json.JSONDecodeError as e:
        print(f"⚠️  Invalid JSON in {prompt_path}: {e}, falling back to database")
    
    # Fallback to database (for overrides/A-B testing)
    return _load_prompt_from_db(mode)

def _load_prompt_from_db(mode: str) -> Dict[str, Any]:
    """Fallback: load from Supabase role_prompts table"""
    if prompts_supabase is None:
        raise RuntimeError("Supabase client not configured and no JSON file found")
    
    res = (
        prompts_supabase.table("role_prompts")
        .select("content, version")
        .eq("mode", mode)
        .eq("active", True)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    
    if res.data:
        # Convert legacy text prompt to minimal spec
        return {
            "version": res.data[0].get("version", "legacy"),
            "role": mode,
            "persona": res.data[0]["content"],  # Use full content as persona for legacy
            "task": "",
            "format": [],
            "safety": "",
            "extras": {}
        }
    
    raise ValueError(f"No prompt found for mode '{mode}' in JSON or database")

# -------------------------------------------------------------------
# Auto-generated tools documentation
# -------------------------------------------------------------------

def generate_tools_block(tools: List[Dict[str, Any]]) -> str:
    """
    Generate tools documentation from tool catalog
    
    Args:
        tools: List of tool dictionaries with 'name', 'description', 'parameters'
        
    Returns:
        Formatted tools documentation block
    """
    if not tools:
        return "No tools available."
    
    lines = ["Tools you can call:"]
    
    for tool in tools:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "No description")
        params = tool.get("parameters", {}).get("properties", {})
        
        # Build parameter list
        param_strs = []
        for param_name, param_info in params.items():
            param_type = param_info.get("type", "any")
            param_strs.append(f"{param_name}={param_type}")
        
        param_list = ", ".join(param_strs) if param_strs else ""
        lines.append(f"• {name}({param_list}) – {desc}")
    
    return "\n".join(lines)

# -------------------------------------------------------------------
# System prompt assembly
# -------------------------------------------------------------------

def build_system_prompt(
    mode: str, 
    sheet_summary: str = "", 
    tools: List[Dict[str, Any]] = None
) -> str:
    """
    Assemble the complete system prompt from P-T-C-F components
    
    Args:
        mode: 'ask' or 'analyst'
        sheet_summary: Current sheet context
        tools: Available tools for auto-documentation
        
    Returns:
        Complete system prompt string
    """
    spec = load_prompt_spec(mode)
    tools = tools or []
    
    # Generate tools documentation
    tools_block = generate_tools_block(tools)
    
    # Context section
    context_parts = []
    if sheet_summary:
        context_parts.append(f"Current sheet: {sheet_summary}")
    
    context = " ".join(context_parts) if context_parts else "Working with a spreadsheet."
    
    # Assemble sections following P-T-C-F structure
    sections = [
        f"PERSONA: {spec['persona']}",
        f"TASK: {spec['task']}",
        f"CONTEXT: {context}",
        f"TOOLS:\n{tools_block}",
        "THINKING: Think step-by-step and use tools before answering.",
        f"OUTPUT: {' '.join(spec['format'])}",
        f"SAFETY: {spec['safety']}"
    ]
    
    # Add examples if present
    if spec.get("examples"):
        examples_lines = ["EXAMPLES:"]
        for ex in spec["examples"]:
            examples_lines.append(f"Request: {ex['request']}")
            examples_lines.append(f"Response: {ex['assistant_reply']}")
            examples_lines.append("")
        sections.append("\n".join(examples_lines))
    
    return "\n\n".join(sections)

# -------------------------------------------------------------------
# Migration helpers
# -------------------------------------------------------------------

def export_current_prompts_to_json():
    """Export current Supabase prompts to JSON format for migration"""
    if prompts_supabase is None:
        print("⚠️  Supabase client not configured")
        return
    
    # Export both ask and analyst
    for mode in ["ask", "analyst"]:
        try:
            res = (
                prompts_supabase.table("role_prompts")
                .select("content, version")
                .eq("mode", mode)
                .eq("active", True)
                .limit(1)
                .execute()
            )
            
            if res.data:
                content = res.data[0]["content"]
                version = res.data[0].get("version", "1.0")
                
                # Create basic JSON structure from legacy content
                legacy_spec = {
                    "version": f"legacy_{version}",
                    "role": mode,
                    "persona": "Legacy prompt (needs restructuring)",
                    "task": content,  # Put full content in task for now
                    "format": ["Provide clear, helpful responses"],
                    "safety": "Follow standard AI safety guidelines",
                    "extras": {"migrated_from": "supabase_role_prompts"}
                }
                
                # Save to file
                output_path = Path("docs/prompts") / f"{mode}_legacy.json"
                with open(output_path, 'w') as f:
                    json.dump(legacy_spec, f, indent=2)
                
                print(f"✅ Exported {mode} prompt to {output_path}")
            else:
                print(f"⚠️  No active {mode} prompt found in database")
                
        except Exception as e:
            print(f"❌ Error exporting {mode} prompt: {e}")

# -------------------------------------------------------------------
# Backward compatibility
# -------------------------------------------------------------------

def get_active_prompt(mode: str) -> str:
    """
    Backward compatibility function - returns assembled prompt as string
    This maintains compatibility with existing BaseAgent code
    """
    return build_system_prompt(mode)

# -------------------------------------------------------------------
# Admin compatibility functions (for role_prompts table management)
# -------------------------------------------------------------------

def list_prompts(mode: str) -> List[Dict[str, Any]]:
    """
    Compatibility function for admin endpoints.
    Return all stored versions for admin UI (latest first) from role_prompts table.
    """
    if prompts_supabase is None:
        return []
    
    try:
        res = (
            prompts_supabase.table("role_prompts")
            .select("*")
            .eq("mode", mode)
            .order("version", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"Error listing prompts for mode {mode}: {e}")
        return []

def create_prompt(mode: str, text: str, created_by: str, version: str = "v1.0") -> Dict[str, Any]:
    """
    Compatibility function for admin endpoints.
    Insert new prompt version and make it active in role_prompts table.
    Previous active version is automatically de-activated.
    """
    if prompts_supabase is None:
        raise RuntimeError("Supabase client not configured")
    
    try:
        # deactivate older active prompt
        prompts_supabase.table("role_prompts") \
            .update({"active": False}) \
            .eq("mode", mode) \
            .eq("active", True) \
            .execute()

        result = prompts_supabase.table("role_prompts").insert({
            "mode": mode,
            "content": text,
            "version": version,
            "active": True,
            "inserted_at": "now()"
        }).execute()

        return result.data[0] if result.data else {}
    except Exception as e:
        print(f"Error creating prompt for mode {mode}: {e}")
        raise 