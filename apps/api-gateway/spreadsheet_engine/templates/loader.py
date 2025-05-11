import copy, json, zlib, base64
from pathlib import Path
from workbook_store import Workbook
from spreadsheet_engine.model import Spreadsheet  # noqa

COMPILED_DIR = Path(__file__).parents[2] / "assets" / "templates_compiled"
_cache: dict[str, dict] = {}

def _load(name: str) -> dict:
    """Load and parse a compiled template from JSON."""
    if name in _cache:
        return _cache[name]
    try:
        data = (COMPILED_DIR / f"{name}.json").read_bytes()
        tpl = json.loads(zlib.decompress(base64.b64decode(data)))
        _cache[name] = tpl
        return tpl
    except Exception as e:
        raise ValueError(f"Failed to load template {name}: {e}")

def insert_template(wb: Workbook, tpl_name: str, prefix: str | None = None):
    """
    Copy a pre-compiled template into the workbook.
    
    Args:
        wb: Target workbook to insert sheets into
        tpl_name: Template name (without .json extension)
        prefix: Optional prefix for sheet names to avoid collisions
    
    Returns:
        Dictionary with status and sheet list
    """
    tpl = _load(tpl_name)
    inserted_sheets = []
    
    for sheet_title, meta in tpl.items():
        new_title = f"{prefix}_{sheet_title}" if prefix else sheet_title
        
        # Check for existing sheet
        if new_title in wb.list_sheets():
            raise ValueError(f"Sheet {new_title} already exists in workbook")
            
        # Create new sheet and populate cells
        sheet = wb.new_sheet(new_title)
        inserted_sheets.append(new_title)
        
        # Transfer all cells from template
        for r, row in enumerate(meta["cells"]):
            for c, val in enumerate(row):
                if val is None:
                    continue
                    
                # Get cell reference (A1, B2, etc)
                col = sheet._index_to_column(c)
                cell_ref = f"{col}{r+1}"
                
                # Set cell value (formulas will be recognized by the '=' prefix)
                sheet.set_cell(cell_ref, val)
    
    # Make sure cross-sheet formulas are updated
    wb.recalculate()
    
    return {
        "status": "inserted", 
        "sheets": inserted_sheets
    }
