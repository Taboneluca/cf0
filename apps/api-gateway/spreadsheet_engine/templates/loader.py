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
        # Try to read the file using read_text instead of read_bytes for better error handling
        template_path = COMPILED_DIR / f"{name}.json"
        if not template_path.exists():
            raise ValueError(f"Template {name} does not exist")
            
        # Read and parse the template
        data = template_path.read_text(encoding='utf-8')
        tpl = json.loads(data)  # Simplified - no zlib/base64 decoding if not needed
        
        _cache[name] = tpl
        return tpl
    except FileNotFoundError:
        raise ValueError(f"Template {name} does not exist")
    except Exception as e:
        raise ValueError(f"Failed to load template {name}: {e}")

def describe_template(template: str):
    """
    Return sheet names, dimensions and key header rows of a template.
    
    Args:
        template: Template name (without .json extension)
    
    Returns:
        Dictionary with metadata for each sheet
    """
    try:
        tpl = _load(template)
        return {
            s: {
                "rows": meta["n_rows"],
                "cols": meta["n_cols"],
                "first_row": meta["cells"][0] if meta["cells"] else []
            } for s, meta in tpl.items()
        }
    except Exception as e:
        # Return a friendly error message instead of raising an exception
        return {
            "error": str(e),
            "template": template,
            "available_templates": ["fsm", "dcf"]  # List of known templates
        }

def preview_cells(template: str, sheet: str, range: str):
    """
    Preview cells from a template without inserting anything.
    
    Args:
        template: Template name (without .json extension)
        sheet: Sheet name within the template
        range: A1-style range (e.g., A1:C10)
        
    Returns:
        2D array of cell values in the requested range
    """
    from spreadsheet_engine.utils import a1_to_range  # helper already used elsewhere
    tpl = _load(template)
    if sheet not in tpl:
        return {"error": f"Sheet '{sheet}' not found in template '{template}'"}
    
    cells = tpl[sheet]["cells"]
    try:
        r1, c1, r2, c2 = a1_to_range(range)
        return [row[c1:c2+1] for row in cells[r1:r2+1]]
    except Exception as e:
        return {"error": f"Error parsing range: {str(e)}"}

def insert_template_sheets(wb: Workbook, template: str, sheets: list[str], prefix: str | None = None):
    """
    Copy specific sheets from a template into the workbook.
    
    Args:
        wb: Target workbook to insert sheets into
        template: Template name (without .json extension)
        sheets: List of sheet names to insert
        prefix: Optional prefix for sheet names to avoid collisions
        
    Returns:
        Dictionary with status and sheet list
    """
    tpl = _load(template)
    missing = [s for s in sheets if s not in tpl]
    if missing:
        return {"error": f"Sheets not found in template: {missing}"}
    
    inserted_sheets = []
    for s in sheets:
        result = insert_template(wb, template, prefix=prefix, only_sheet=s)
        inserted_sheets.extend(result["sheets"])
    
    return {"status": "inserted", "sheets": inserted_sheets}

def insert_template(wb: Workbook, tpl_name: str, prefix: str | None = None, only_sheet: str | None = None):
    """
    Copy a pre-compiled template into the workbook.
    
    Args:
        wb: Target workbook to insert sheets into
        tpl_name: Template name (without .json extension)
        prefix: Optional prefix for sheet names to avoid collisions
        only_sheet: If provided, only insert this specific sheet
    
    Returns:
        Dictionary with status and sheet list
    """
    tpl = _load(tpl_name)
    inserted_sheets = []
    skipped_sheets = []
    
    # Filter to specific sheet if requested
    if only_sheet:
        if only_sheet not in tpl:
            return {"error": f"Sheet '{only_sheet}' not found in template '{tpl_name}'", "status": "error"}
        sheet_items = [(only_sheet, tpl[only_sheet])]
    else:
        sheet_items = tpl.items()
    
    for sheet_title, meta in sheet_items:
        new_title = f"{prefix}{sheet_title}" if prefix else sheet_title
        
        # Check for existing sheet - instead of raising exception, track as skipped
        if new_title in wb.list_sheets():
            skipped_sheets.append(new_title)
            continue
            
        # Create new sheet and populate cells
        try:
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
        except Exception as e:
            return {"error": f"Error creating sheet {new_title}: {str(e)}", "status": "error"}
    
    # Make sure cross-sheet formulas are updated
    wb.recalculate()
    
    # If we skipped any sheets due to duplicates, include in response
    if skipped_sheets:
        return {
            "status": "partial", 
            "sheets": inserted_sheets,
            "skipped": skipped_sheets,
            "message": f"Some sheets already existed and were skipped: {', '.join(skipped_sheets)}"
        }
    
    return {
        "status": "inserted", 
        "sheets": inserted_sheets
    }
