import os
import json
import hashlib
from typing import Dict, Any
from .model import Spreadsheet

def sheet_summary(sheet: Spreadsheet, sample_rows=None):
    """
    Create a compact summary of the sheet that drastically reduces token count.
    
    Args:
        sheet: The spreadsheet to summarize
        sample_rows: Number of sample rows to include (default: uses env var SUMMARY_SAMPLE_ROWS or 5)
        
    Returns:
        Dict with sheet summary information including:
        - name: Sheet name
        - n_rows: Number of rows
        - n_cols: Number of columns
        - headers: Column headers
        - sample: Sample rows (first N rows)
        - hash: Content hash for change detection
    """
    # Add null check for sheet
    if sheet is None:
        return {
            "name": "Unknown",
            "n_rows": 0,
            "n_cols": 0,
            "headers": [],
            "sample": [],
            "hash": ""
        }
        
    if sample_rows is None:
        sample_rows = int(os.getenv("SUMMARY_SAMPLE_ROWS", "5"))
    
    # Get the last column letter
    last_col = sheet._index_to_column(sheet.n_cols - 1)
    
    # Get sample rows (using sheet's get_range method)
    sample_data = sheet.get_range(f"A1:{last_col}{sample_rows}")
    
    # Create a hash of the sheet cells for change detection
    cells_json = json.dumps(sheet.cells, default=str)
    content_hash = hashlib.sha256(cells_json.encode()).hexdigest()[:12]
    
    return {
        "name": sheet.name,
        "n_rows": sheet.n_rows,
        "n_cols": sheet.n_cols,
        "headers": sheet.headers,
        "sample": sample_data,
        "hash": content_hash
    } 