import json
import hashlib
import os
from typing import Dict, Any
from .model import Spreadsheet

def sheet_summary(sheet: Spreadsheet, sample_rows=None) -> Dict[str, Any]:
    """
    Create a compact summary of a sheet instead of full serialization.
    
    Args:
        sheet: The spreadsheet to summarize
        sample_rows: Number of rows to sample (default from env var SUMMARY_SAMPLE_ROWS or 5)
        
    Returns:
        Dict with sheet dimensions, headers, sample rows, and a hash
    """
    if sample_rows is None:
        sample_rows = int(os.getenv("SUMMARY_SAMPLE_ROWS", "5"))
    
    # If the sheet has fewer rows than sample_rows, adjust accordingly
    sample_rows = min(sample_rows, sheet.n_rows)
    
    # Get column reference for the last column
    last_col = sheet._index_to_column(sheet.n_cols - 1)
    
    # Get sample rows
    sample = sheet.get_range(f"A1:{last_col}{sample_rows}") if sample_rows > 0 else []
    
    # Generate a hash of the sheet content for easy change detection
    hash_str = hashlib.sha256(json.dumps(sheet.cells, default=str).encode()).hexdigest()[:12]
    
    # Return summary
    return {
        "name": sheet.name,
        "n_rows": sheet.n_rows,
        "n_cols": sheet.n_cols,
        "headers": sheet.headers,
        "sample": sample,
        "hash": hash_str,
        "non_empty_cells": sum(1 for row in sheet.cells for cell in row if cell is not None)
    } 