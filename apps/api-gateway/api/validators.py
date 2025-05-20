"""
Validator functions for checking update operations against business rules.
"""
from typing import List, Dict, Any, Optional
import re


def _parse_cell_reference(cell_ref: str) -> tuple[str, int]:
    """
    Parses a cell reference like 'A1', 'B2', etc. into column and row components.
    
    Args:
        cell_ref: A cell reference string (e.g., 'A1', 'Z30')
        
    Returns:
        Tuple of (column_letter, row_number)
        
    Raises:
        ValueError: If the cell reference format is invalid
    """
    # Strip any sheet reference (Sheet1!A1 -> A1)
    if '!' in cell_ref:
        cell_ref = cell_ref.split('!', 1)[1]
    
    # Use regex to match column letters and row numbers
    match = re.match(r'^([A-Za-z]+)(\d+)$', cell_ref)
    if not match:
        raise ValueError(f"Invalid cell reference format: {cell_ref}")
    
    col_letters = match.group(1).upper()
    row_number = int(match.group(2))
    
    return col_letters, row_number


def _column_index(col_letters: str) -> int:
    """
    Converts a column letter (A, B, ..., Z, AA, AB, ...) to its index (0, 1, ...)
    
    Args:
        col_letters: Column letter(s) (e.g., 'A', 'Z', 'AA')
        
    Returns:
        Zero-based column index
    """
    result = 0
    for letter in col_letters:
        result = result * 26 + (ord(letter.upper()) - ord('A') + 1)
    return result - 1  # Convert to 0-based


def _is_formula(value: Any) -> bool:
    """
    Check if a value appears to be a formula.
    
    Args:
        value: Any cell value
        
    Returns:
        True if the value looks like a formula, False otherwise
    """
    if not isinstance(value, str):
        return False
    
    # Formulas typically start with '='
    return value.strip().startswith('=')


def validate_updates(updates: List[Dict[str, Any]]) -> None:
    """
    Validates a list of cell updates against business rules.
    
    Rules:
    1. Cell references must be within range (max: J30)
    2. No formulas unless explicitly marked
    
    Args:
        updates: List of update objects with at least 'cell' and 'value'/'new' keys
        
    Raises:
        ValueError: If any validation rule is violated
    """
    if not updates:
        return  # No updates to validate
    
    MAX_ROW = 30
    MAX_COL = 9  # J is the 10th letter (index 9)
    
    # Check if the user's message explicitly requested formulas
    formulas_requested = False
    for update in updates:
        if update.get('allow_formula', False) or update.get('allow_formulas', False):
            formulas_requested = True
            break
    
    for update in updates:
        # Skip updates without cell reference
        if not isinstance(update, dict) or 'cell' not in update:
            continue
        
        cell_ref = update['cell']
        
        # Get the value (handle different key names)
        value = update.get('value', update.get('new_value', update.get('new', None)))
        
        try:
            # Parse the cell reference
            col_letters, row = _parse_cell_reference(cell_ref)
            col_index = _column_index(col_letters)
            
            # Check row bounds
            if row > MAX_ROW:
                raise ValueError(
                    f"Cell {cell_ref} exceeds maximum allowed row ({MAX_ROW}). "
                    f"Please use cells within the first {MAX_ROW} rows only."
                )
            
            # Check column bounds
            if col_index > MAX_COL:
                raise ValueError(
                    f"Cell {cell_ref} exceeds maximum allowed column (J). "
                    f"Please use columns A-J only."
                )
            
            # Check for formulas (if formula usage isn't explicitly allowed)
            # Allow formulas if they've been explicitly requested
            formula_allowed = update.get('allow_formula', False) or formulas_requested
            if not formula_allowed and _is_formula(value):
                raise ValueError(
                    f"Formula detected in cell {cell_ref} but formulas are not requested. "
                    f"Please use plain values unless formulas are specifically needed."
                )
            
        except Exception as e:
            if isinstance(e, ValueError) and str(e).startswith("Cell"):
                # Re-raise our custom validation errors
                raise
            else:
                # Wrap other errors
                raise ValueError(f"Error validating cell {cell_ref}: {str(e)}")
    
    return  # All validations passed 