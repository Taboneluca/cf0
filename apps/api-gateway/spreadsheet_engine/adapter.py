"""
Adapter module to support switching between different spreadsheet implementations.

This module provides a feature flag mechanism to switch between:
1. The original list-based spreadsheet model
2. The new pandas DataFrame-based model with optimized performance

It handles conversion between the two models to ensure compatibility.
"""

import os
from typing import Dict, Any, Optional

# Import both implementations
from .model import Spreadsheet as ListSpreadsheet
from .dataframe_model import DataFrameSpreadsheet

# Feature flags
USE_DATAFRAME_MODEL = os.getenv("USE_DATAFRAME_MODEL", "0").lower() in ("1", "true", "yes")
USE_FORMULA_ENGINE = os.getenv("USE_FORMULA_ENGINE", "0").lower() in ("1", "true", "yes")

# We need to maintain the same API regardless of the implementation
class SpreadsheetAdapter:
    """Adapter that provides a consistent interface regardless of the underlying implementation."""
    
    @staticmethod
    def create_sheet(rows: int = 100, cols: int = 30, name: str = "Sheet1") -> Any:
        """Create a new spreadsheet using the selected implementation"""
        if USE_DATAFRAME_MODEL:
            return DataFrameSpreadsheet(rows=rows, cols=cols, name=name)
        else:
            return ListSpreadsheet(rows=rows, cols=cols, name=name)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Any:
        """Create a spreadsheet from a dictionary representation"""
        if USE_DATAFRAME_MODEL:
            return DataFrameSpreadsheet.from_dict(data)
        else:
            return ListSpreadsheet.from_dict(data)
    
    @staticmethod
    def convert_if_needed(sheet: Any) -> Any:
        """Ensure the sheet is using the correct implementation"""
        if USE_DATAFRAME_MODEL and isinstance(sheet, ListSpreadsheet):
            # Convert from list-based to DataFrame-based model
            df_sheet = DataFrameSpreadsheet(rows=1, cols=1, name=sheet.name)
            return df_sheet.from_original_model(sheet)
        elif not USE_DATAFRAME_MODEL and isinstance(sheet, DataFrameSpreadsheet):
            # Convert from DataFrame-based to list-based model
            list_sheet = ListSpreadsheet(rows=1, cols=1, name=sheet.name) 
            df_sheet.to_original_model(list_sheet)
            return list_sheet
        else:
            # No conversion needed, return as is
            return sheet

def get_implementation_info() -> Dict[str, Any]:
    """Return information about the current implementation for debugging"""
    return {
        "using_dataframe_model": USE_DATAFRAME_MODEL,
        "using_formula_engine": USE_FORMULA_ENGINE
    } 