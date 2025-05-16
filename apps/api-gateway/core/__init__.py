"""
Shim that lets the rest of the code keep using
    from core.sheets import …
    from core.agents import …
    from core.llm import …
without moving any files.

The real code still lives in the top-level packages
`spreadsheet_engine`, `agents`, and `llm`.
"""
import importlib, sys, types

# reference to this very module
_this = sys.modules[__name__]

# map real-package → alias-under-core
_aliases = {
    "spreadsheet_engine": "sheets",
    "agents": "agents",
    "llm": "llm",
}

for real_pkg, alias in _aliases.items():
    try:
        mod = importlib.import_module(real_pkg)
        sys.modules[f"{__name__}.{alias}"] = mod     # register as core.<alias>
        setattr(_this, alias, mod)                  # expose as attribute
    except ImportError:
        # optional deps might be missing in some builds; fail gracefully
        pass 