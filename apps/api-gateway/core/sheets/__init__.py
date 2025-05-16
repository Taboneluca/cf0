from .model import DEFAULT_ROWS, DEFAULT_COLS  
from .adapter import SpreadsheetAdapter, USE_DATAFRAME_MODEL, USE_FORMULA_ENGINE
# Break circular import by using lazy imports
# from workbook_store import get_workbook, get_sheet
from .summary import sheet_summary
from .operations import (
    # Read operations
    get_cell,
    get_range,
    summarize_sheet,
    calculate,
    get_row_by_header,
    get_column_by_header,
    col_to_idx,
    
    # Write operations
    set_cell,
    add_row,
    add_column,
    delete_row,
    delete_column,
    sort_range,
    find_replace,
    create_new_sheet,
    apply_scalar_to_row,
    apply_scalar_to_column
)

# Use the adapter to expose the current implementation
Spreadsheet = SpreadsheetAdapter.create_sheet

# Define lazy loaded functions to avoid circular imports
def get_workbook(wid: str):
    """Lazy import to avoid circular dependency"""
    from workbook_store import get_workbook as _get_workbook
    return _get_workbook(wid)

def get_sheet(wid: str, sid: str):
    """Lazy import to avoid circular dependency"""
    from workbook_store import get_sheet as _get_sheet
    return _get_sheet(wid, sid)

__all__ = [
    'Spreadsheet',
    'DEFAULT_ROWS',
    'DEFAULT_COLS',
    'get_workbook',
    'get_sheet',
    'get_cell',
    'get_range',
    'summarize_sheet',
    'sheet_summary',
    'calculate',
    'get_row_by_header',
    'get_column_by_header',
    'col_to_idx',
    'set_cell',
    'add_row',
    'add_column',
    'delete_row',
    'delete_column',
    'sort_range',
    'find_replace',
    'create_new_sheet',
    'apply_scalar_to_row',
    'apply_scalar_to_column',
    'USE_DATAFRAME_MODEL',
    'USE_FORMULA_ENGINE',
    'SpreadsheetAdapter'
] 