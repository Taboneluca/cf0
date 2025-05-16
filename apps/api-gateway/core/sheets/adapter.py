"""
Adapter module to support switching between different spreadsheet implementations.

This module provides a feature flag mechanism to switch between:
1. The original list-based spreadsheet model
2. The new pandas DataFrame-based model with optimized performance

It handles conversion between the two models to ensure compatibility.
"""

import os
import time
from typing import Dict, Any, Optional

# Import both implementations
from .model import Spreadsheet as ListSpreadsheet
from .dataframe_model import DataFrameSpreadsheet

# Feature flags
USE_DATAFRAME_MODEL = os.getenv("USE_DATAFRAME_MODEL", "0").lower() in ("1", "true", "yes")
USE_FORMULA_ENGINE = os.getenv("USE_FORMULA_ENGINE", "0").lower() in ("1", "true", "yes")
USE_FORMULA_CACHE = True  # Always cache formulas for better performance
USE_OPTIMIZED_SERIALIZATION = True  # Always use optimized serialization

# Log the active configuration on module load
print(f"📊 Spreadsheet Engine Configuration:")
print(f"   → DataFrame Model: {'✅ ENABLED' if USE_DATAFRAME_MODEL else '❌ DISABLED'}")
print(f"   → Formula Engine: {'✅ ENABLED' if USE_FORMULA_ENGINE else '❌ DISABLED'}")
print(f"   → Incremental Recalc: {'✅ ENABLED' if os.getenv('USE_INCREMENTAL_RECALC', '1').lower() in ('1', 'true', 'yes') else '❌ DISABLED'}")
print(f"   → Formula Cache: {'✅ ENABLED' if USE_FORMULA_CACHE else '❌ DISABLED'}")
print(f"   → Optimized Serialization: {'✅ ENABLED' if USE_OPTIMIZED_SERIALIZATION else '❌ DISABLED'}")
print(f"   → Pandas Version: {__import__('pandas').__version__}")
print(f"   → NumPy Version: {__import__('numpy').__version__}")

# Enable Pandas vectorized operations for better performance
import pandas as pd
pd.set_option('compute.use_numexpr', True)  # Enable vectorized operations
pd.set_option('mode.chained_assignment', None)  # Disable warnings for performance

# We need to maintain the same API regardless of the implementation
class SpreadsheetAdapter:
    """Adapter that provides a consistent interface regardless of the underlying implementation."""
    
    @staticmethod
    def create_sheet(rows: int = 100, cols: int = 30, name: str = "Sheet1") -> Any:
        """Create a new spreadsheet using the selected implementation"""
        start_time = time.time()
        if USE_DATAFRAME_MODEL:
            sheet = DataFrameSpreadsheet(rows=rows, cols=cols, name=name)
            print(f"🔄 Created DataFrame-based sheet '{name}' ({rows}x{cols}) in {(time.time() - start_time)*1000:.1f}ms")
            return sheet
        else:
            sheet = ListSpreadsheet(rows=rows, cols=cols, name=name)
            print(f"🔄 Created List-based sheet '{name}' ({rows}x{cols}) in {(time.time() - start_time)*1000:.1f}ms")
            return sheet
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Any:
        """Create a spreadsheet from a dictionary representation"""
        start_time = time.time()
        if USE_DATAFRAME_MODEL:
            sheet = DataFrameSpreadsheet.from_dict(data)
            print(f"🔄 Loaded DataFrame-based sheet '{sheet.name}' from dict in {(time.time() - start_time)*1000:.1f}ms")
            return sheet
        else:
            sheet = ListSpreadsheet.from_dict(data)
            print(f"🔄 Loaded List-based sheet '{sheet.name}' from dict in {(time.time() - start_time)*1000:.1f}ms")
            return sheet
    
    @staticmethod
    def convert_if_needed(sheet: Any) -> Any:
        """Ensure the sheet is using the correct implementation"""
        if USE_DATAFRAME_MODEL and isinstance(sheet, ListSpreadsheet):
            # Convert from list-based to DataFrame-based model
            start_time = time.time()
            print(f"🔄 Converting List-based sheet '{sheet.name}' to DataFrame model...")
            df_sheet = DataFrameSpreadsheet(rows=1, cols=1, name=sheet.name)
            result = df_sheet.from_original_model(sheet)
            print(f"✅ Conversion completed in {(time.time() - start_time)*1000:.1f}ms")
            return result
        elif not USE_DATAFRAME_MODEL and isinstance(sheet, DataFrameSpreadsheet):
            # Convert from DataFrame-based to list-based model
            start_time = time.time()
            print(f"🔄 Converting DataFrame-based sheet '{sheet.name}' to List model...")
            list_sheet = ListSpreadsheet(rows=1, cols=1, name=sheet.name) 
            df_sheet.to_original_model(list_sheet)
            print(f"✅ Conversion completed in {(time.time() - start_time)*1000:.1f}ms")
            return list_sheet
        else:
            # No conversion needed, return as is
            return sheet

def get_implementation_info() -> Dict[str, Any]:
    """Return information about the current implementation for debugging"""
    return {
        "using_dataframe_model": USE_DATAFRAME_MODEL,
        "using_formula_engine": USE_FORMULA_ENGINE,
        "incremental_recalc": os.getenv("USE_INCREMENTAL_RECALC", "1").lower() in ("1", "true", "yes"),
        "formula_cache": USE_FORMULA_CACHE,
        "optimized_serialization": USE_OPTIMIZED_SERIALIZATION,
        "model_type": "DataFrame" if USE_DATAFRAME_MODEL else "List-based",
        "formula_engine": "Excel-parity" if USE_FORMULA_ENGINE else "Basic",
        "pandas_version": __import__('pandas').__version__,
        "numpy_version": __import__('numpy').__version__
    } 