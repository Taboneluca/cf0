from typing import List, Dict, Any, Optional, Union, Tuple
from .model import Spreadsheet, get_sheet, sheets, DEFAULT_ROWS, DEFAULT_COLS
from workbook_store import get_workbook, get_sheet as get_workbook_sheet

# Read operations (used by AskAgent)

def get_cell(cell_ref: str, sheet=None) -> Any:
    """Get the value of a specific cell"""
    return sheet.get_cell(cell_ref)

def get_range(range_ref: str, sheet=None) -> List[List[Any]]:
    """Get the values in a range of cells"""
    return sheet.get_range(range_ref)

def summarize_sheet(sheet=None) -> Dict[str, Any]:
    """Get summary information about the spreadsheet"""
    return {
        "name": sheet.name,
        "rows": sheet.n_rows,
        "columns": sheet.n_cols,
        "headers": sheet.headers,
        "non_empty_cells": sum(1 for row in sheet.cells for cell in row if cell is not None)
    }

def calculate(formula: str, sheet=None) -> Any:
    """
    Evaluate a simple formula on the spreadsheet data
    
    Example formulas:
    - "SUM(A1:A10)"
    - "AVERAGE(B2:B5)"
    - "MAX(C1:C20)"
    """
    import re
    
    try:
        # Replace cell refs with their numeric values, then eval safely
        expr = re.sub(r'([A-Za-z]+[0-9]+)',
                      lambda m: str(get_cell(m.group(1), sheet) or 0),
                      formula.lstrip('='))
        return eval(expr, {"__builtins__": {}}, {})
    except Exception:
        raise ValueError(f"Invalid formula format: {formula}")

# Write operations (used by AnalystAgent)

def set_cell(cell_ref: str, value: Any, sheet=None) -> Dict[str, Any]:
    """Set the value of a specific cell"""
    print(f'[{sheet.name}] {cell_ref} <- {value}')  # Log cell update
    old_value = get_cell(cell_ref, sheet)
    print(f"Setting cell {cell_ref} from '{old_value}' to '{value}' in sheet {sheet.name}")
    sheet.set_cell(cell_ref, value)
    return {
        "cell": cell_ref,
        "old_value": old_value,
        "new": value
    }

def set_cells(updates: list[dict[str, Any]], sheet=None):
    """
    Apply many cell updates at once
    
    Args:
        updates: List of update dictionaries, each containing 'cell' and 'value'
        sheet: The sheet to update
        
    Returns:
        List of changes made to cells
    """
    print(f'[{sheet.name}] bulk set_cells: {updates}')  # Log bulk updates
    changed = []
    for u in updates:
        changed.append(set_cell(u["cell"], u["value"], sheet))
    return {"updates": changed}

def add_row(values: Optional[List[Any]] = None, sheet=None, row_index: Optional[int] = None) -> Dict[str, Any]:
    """
    Add a new row to the spreadsheet
    
    Args:
        values: The values to add to the row
        sheet: The sheet to add the row to
        row_index: The index to insert the row at (0-based). If None, adds to the end.
    """
    # Default to adding at the end if row_index not specified
    if row_index is None:
        row_index = sheet.n_rows  # This will be the index of the new row
    
    # Ensure we don't exceed reasonable limits - prefer early rows
    if row_index > 5 and sheet.n_rows < 10:
        # If data is being added beyond row 5 but sheet has empty rows,
        # move it to the beginning
        row_index = 1
    
    # Handle the row insertion
    if values is None:
        values = [None] * sheet.n_cols
    
    # Pad or truncate values to match column count
    if len(values) < sheet.n_cols:
        values = values + [None] * (sheet.n_cols - len(values))
    elif len(values) > sheet.n_cols:
        values = values[:sheet.n_cols]
    
    # If inserting at end or beyond, just append
    if row_index >= sheet.n_rows:
        sheet.cells.append(values)
        sheet.n_rows += 1
    else:
        # Insert at specific position
        sheet.cells.insert(row_index, values)
        sheet.n_rows += 1
    
    return {
        "action": "add_row",
        "row_index": row_index,
        "values": values or [None] * sheet.n_cols
    }

def add_column(name: Optional[str] = None, values: Optional[List[Any]] = None, sheet=None) -> Dict[str, Any]:
    """Add a new column to the spreadsheet"""
    col_index = sheet.n_cols  # This will be the index of the new column
    col_letter = sheet._index_to_column(col_index)
    sheet.add_column(name, values)
    return {
        "action": "add_column",
        "column_index": col_index,
        "column_letter": col_letter,
        "name": name or col_letter,
        "values": values or [None] * sheet.n_rows
    }

def delete_row(row_index: int, sheet=None) -> Dict[str, Any]:
    """Delete a row from the spreadsheet"""
    if row_index < 0:
        row_index = sheet.n_rows + row_index  # Support negative indexing
    
    deleted_values = sheet.cells[row_index].copy()
    sheet.delete_row(row_index)
    return {
        "action": "delete_row",
        "row_index": row_index,
        "deleted_values": deleted_values
    }

def delete_column(column_index_or_letter, sheet=None) -> Dict[str, Any]:
    """Delete a column from the spreadsheet"""
    # If column is specified as a letter, convert to index
    if isinstance(column_index_or_letter, str):
        col_index = sheet._column_to_index(column_index_or_letter)
    else:
        col_index = column_index_or_letter
    
    if col_index < 0:
        col_index = sheet.n_cols + col_index  # Support negative indexing
    
    col_letter = sheet._index_to_column(col_index)
    deleted_values = [row[col_index] for row in sheet.cells]
    sheet.delete_column(col_index)
    return {
        "action": "delete_column",
        "column_index": col_index,
        "column_letter": col_letter,
        "deleted_values": deleted_values
    }

def sort_range(range_ref: str, key_col, order: str = "asc", sheet=None) -> Dict[str, Any]:
    """
    Sort a range of cells by a specified key column
    
    Args:
        range_ref: The range to sort (e.g., "A1:C10")
        key_col: The column to sort by (letter or index)
        order: The sort order ("asc" or "desc")
        
    Returns:
        Information about the sorting operation
    """
    # Parse the range
    start_row, start_col, end_row, end_col = sheet._parse_range_ref(range_ref)
    
    # Convert key_col to index relative to the range
    if isinstance(key_col, str):
        key_col_idx = sheet._column_to_index(key_col)
    else:
        key_col_idx = key_col
    
    # Adjust key_col to be relative to the range
    if key_col_idx < start_col or key_col_idx > end_col:
        raise ValueError(f"Key column {key_col} is outside the range {range_ref}")
    
    relative_key_col = key_col_idx - start_col
    
    # Extract the rows in the range
    rows_to_sort = [sheet.cells[r][start_col:end_col+1] for r in range(start_row, end_row+1)]
    
    # Sort the rows
    sorted_rows = sorted(
        rows_to_sort,
        key=lambda row: row[relative_key_col] if row[relative_key_col] is not None else (0 if order == "asc" else float('inf')),
        reverse=(order.lower() == "desc")
    )
    
    # Update the cells in the sheet
    for i, r in enumerate(range(start_row, end_row+1)):
        for j, c in enumerate(range(start_col, end_col+1)):
            sheet.cells[r][c] = sorted_rows[i][j]
    
    return {
        "action": "sort_range",
        "range": range_ref,
        "key_column": key_col,
        "order": order
    }

def find_replace(find_text: str, replace_text: str, sheet=None) -> Dict[str, Any]:
    """
    Find and replace text in the spreadsheet
    
    Args:
        find_text: The text to find
        replace_text: The text to replace it with
        
    Returns:
        Information about the replacements made
    """
    replacements = []
    
    for row_idx, row in enumerate(sheet.cells):
        for col_idx, cell in enumerate(row):
            if cell is not None and isinstance(cell, str) and find_text in cell:
                old_value = cell
                new_value = cell.replace(find_text, replace_text)
                sheet.cells[row_idx][col_idx] = new_value
                cell_ref = f"{sheet._index_to_column(col_idx)}{row_idx+1}"
                replacements.append({
                    "cell": cell_ref,
                    "old_value": old_value,
                    "new_value": new_value
                })
    
    return {
        "action": "find_replace",
        "find_text": find_text,
        "replace_text": replace_text,
        "replacements": replacements,
        "count": len(replacements)
    }

def create_new_sheet(rows: int = DEFAULT_ROWS, cols: int = DEFAULT_COLS, name: str = "Sheet1", sheet=None) -> Dict[str, Any]:
    """Create a new spreadsheet, replacing the current one"""
    print(f"Creating new sheet with name: {name}, rows: {rows}, cols: {cols}")
    new_sheet = Spreadsheet(rows=rows, cols=cols, name=name)
    
    if sheet:
        # If a session sheet was provided, update it
        for sid, s in sheets.items():
            if s == sheet:
                print(f"Updating session sheet for session {sid}")
                sheets[sid] = new_sheet
                break
    else:
        # Update the global sheet
        print("Updating global sheet")
    
    return {
        "action": "new_sheet",
        "name": name,
        "rows": rows,
        "columns": cols
    }

def get_row_by_header(header: str, sheet=None) -> Dict[str, Any]:
    """
    Return a row by its header (first cell value)
    
    Args:
        header: The value to search for in the first cell of each row
        
    Returns:
        Dictionary of cell references and values for the row
    """
    for row_idx, row in enumerate(sheet.cells):
        if row and row[0] == header:
            result = {}
            for col_idx, cell in enumerate(row):
                cell_ref = f"{sheet._index_to_column(col_idx)}{row_idx+1}"
                result[cell_ref] = cell
            return result
    
    return {"error": f"Row with header '{header}' not found"}

def get_column_by_header(header: str, sheet=None) -> Dict[str, Any]:
    """
    Return a column by its header (first row value)
    
    Args:
        header: The value to search for in the first row
        
    Returns:
        Dictionary of cell references and values for the column
    """
    if not sheet.headers or len(sheet.headers) == 0:
        return {"error": "Sheet has no headers"}
    
    # Find the column index
    col_idx = None
    for i, h in enumerate(sheet.headers):
        if h == header:
            col_idx = i
            break
    
    if col_idx is None:
        return {"error": f"Column with header '{header}' not found"}
    
    # Get values from the column
    result = {}
    for row_idx in range(sheet.n_rows):
        cell_ref = f"{sheet._index_to_column(col_idx)}{row_idx+1}"
        result[cell_ref] = sheet.cells[row_idx][col_idx]
    
    return result

def col_to_idx(col_letter: str, sheet=None) -> int:
    """Convert a column letter to an index"""
    return sheet._column_to_index(col_letter)

def apply_scalar_to_row(header: str, factor: float, sheet=None) -> Dict[str, Any]:
    """
    Multiply all numeric cells in a row by a factor
    
    Args:
        header: The first cell value of the row to modify
        factor: The number to multiply by
        
    Returns:
        Information about the cells modified
    """
    # Find the row
    row_info = get_row_by_header(header, sheet)
    if "error" in row_info:
        return row_info
    
    # Apply the scalar to numeric cells
    changes = []
    for cell_ref, value in row_info.items():
        try:
            if value is not None:
                numeric_value = float(value)
                new_value = numeric_value * factor
                changes.append({
                    "cell": cell_ref,
                    "old_value": value,
                    "new_value": new_value
                })
                row_idx, col_idx = sheet._parse_cell_ref(cell_ref)
                sheet.cells[row_idx][col_idx] = new_value
        except (ValueError, TypeError):
            # Skip non-numeric cells
            pass
    
    return {
        "action": "apply_scalar_to_row",
        "header": header,
        "factor": factor,
        "changes": changes
    }

def apply_scalar_to_column(header: str, factor: float, sheet=None) -> Dict[str, Any]:
    """
    Multiply all numeric cells in a column by a factor
    
    Args:
        header: The header of the column to modify
        factor: The number to multiply by
        
    Returns:
        Information about the cells modified
    """
    # Find the column
    col_info = get_column_by_header(header, sheet)
    if "error" in col_info:
        return col_info
    
    # Apply the scalar to numeric cells
    changes = []
    for cell_ref, value in col_info.items():
        try:
            if value is not None:
                numeric_value = float(value)
                new_value = numeric_value * factor
                changes.append({
                    "cell": cell_ref,
                    "old_value": value,
                    "new_value": new_value
                })
                row_idx, col_idx = sheet._parse_cell_ref(cell_ref)
                sheet.cells[row_idx][col_idx] = new_value
        except (ValueError, TypeError):
            # Skip non-numeric cells
            pass
    
    return {
        "action": "apply_scalar_to_column",
        "header": header,
        "factor": factor,
        "changes": changes
    }

# Workbook level operations
def list_sheets(wid: str) -> List[str]:
    """
    Return all sheet names in the current workbook.
    
    Args:
        wid: The workbook ID
    
    Returns:
        List of sheet names
    """
    return get_workbook(wid).list_sheets()

def get_sheet_summary(sid: str, wid: str) -> Dict[str, Any]:
    """
    Return rows, columns, headers & non-empty-cell count for a given sheet.
    
    Args:
        sid: The sheet ID
        wid: The workbook ID
    
    Returns:
        Dictionary with sheet information
    """
    sheet = get_workbook(wid).sheet(sid)
    return summarize_sheet(sheet=sheet) 