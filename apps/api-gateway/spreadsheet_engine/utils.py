"""
Utility functions for spreadsheet operations.
"""
import re
from typing import Tuple, List, Dict, Any, Optional, Union

def a1_to_range(range_ref: str) -> Tuple[int, int, int, int]:
    """
    Parse an Excel-style range reference like 'A1:B10' into row and column indices.
    
    Args:
        range_ref: The range reference to parse (e.g., 'A1:B10' or just 'A1')
        
    Returns:
        Tuple of (start_row, start_col, end_row, end_col) as 0-based indices
    """
    # Check if it's a reference to a single cell
    if ':' not in range_ref:
        # Single cell is treated as a range to itself
        range_ref = f"{range_ref}:{range_ref}"
    
    # Split the range into start and end
    start_ref, end_ref = range_ref.split(':', 1)
    
    # Parse start and end cell references
    start_row, start_col = _parse_cell_ref(start_ref)
    end_row, end_col = _parse_cell_ref(end_ref)
    
    # Ensure start comes before end
    start_row, end_row = min(start_row, end_row), max(start_row, end_row)
    start_col, end_col = min(start_col, end_col), max(start_col, end_col)
    
    return start_row, start_col, end_row, end_col

def _parse_cell_ref(cell_ref: str) -> Tuple[int, int]:
    """
    Parse a cell reference like 'A1' into row and column indices.
    
    Args:
        cell_ref: A cell reference like 'A1' or 'BC123'
        
    Returns:
        Tuple of (row_index, col_index) as 0-based indices
    """
    match = re.match(r'^([A-Za-z]+)(\d+)$', cell_ref)
    if not match:
        raise ValueError(f"Invalid cell reference format: {cell_ref}")
    
    col_str, row_str = match.groups()
    col_str = col_str.upper()  # Convert to uppercase for consistency
    col_index = _column_to_index(col_str)
    row_index = int(row_str) - 1  # Convert to 0-based index
    
    return row_index, col_index

def _column_to_index(column: str) -> int:
    """
    Convert an Excel-style column name to 0-based index.
    
    Args:
        column: Column name (e.g., 'A', 'B', 'AA', 'BC')
        
    Returns:
        0-based column index
    """
    result = 0
    column = column.upper()  # Ensure uppercase for consistency
    for char in column:
        result = result * 26 + (ord(char) - ord('A') + 1)
    return result - 1

def _index_to_column(index: int) -> str:
    """
    Convert a 0-based column index to Excel-style column name.
    
    Args:
        index: 0-based column index
        
    Returns:
        Column name (e.g., 'A', 'B', 'AA', 'BC')
    """
    import string
    result = ""
    while index >= 0:
        result = string.ascii_uppercase[index % 26] + result
        index = index // 26 - 1
    return result

def range_to_a1(start_row: int, start_col: int, end_row: int, end_col: int) -> str:
    """
    Convert row and column indices to Excel-style range reference.
    
    Args:
        start_row: Start row index (0-based)
        start_col: Start column index (0-based)
        end_row: End row index (0-based)
        end_col: End column index (0-based)
        
    Returns:
        Range reference (e.g., 'A1:B10')
    """
    start_col_str = _index_to_column(start_col)
    end_col_str = _index_to_column(end_col)
    
    # Convert back to 1-based indices for Excel-style references
    start_row_str = str(start_row + 1)
    end_row_str = str(end_row + 1)
    
    start_ref = f"{start_col_str}{start_row_str}"
    end_ref = f"{end_col_str}{end_row_str}"
    
    return f"{start_ref}:{end_ref}"

def is_valid_cell_ref(cell_ref: str) -> bool:
    """Check if a string is a valid cell reference"""
    return bool(re.match(r'^[A-Za-z]+\d+$', cell_ref))

def is_valid_range_ref(range_ref: str) -> bool:
    """Check if a string is a valid range reference"""
    if ':' not in range_ref:
        return is_valid_cell_ref(range_ref)
    
    start_ref, end_ref = range_ref.split(':', 1)
    return is_valid_cell_ref(start_ref) and is_valid_cell_ref(end_ref) 