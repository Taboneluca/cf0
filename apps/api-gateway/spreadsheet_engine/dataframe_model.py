import pandas as pd
import numpy as np
import re
import string
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from collections import defaultdict

# Cell reference patterns - reused from original model
CELL_RE = re.compile(r"([A-Za-z]+)(\d+)", re.I)  # Matches A1, b2, etc.
XREF_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)!([A-Za-z]+)(\d+)", re.I)  # Matches Sheet2!A1

class DataFrameSpreadsheet:
    """
    A Spreadsheet implementation based on pandas DataFrame.
    This provides better performance for large sheets and vectorized operations.
    """
    
    def __init__(self, rows: int = 100, cols: int = 30, name: str = "Sheet1"):
        """
        Initialize a new DataFrame-based spreadsheet.
        
        Args:
            rows: Number of rows in the sheet
            cols: Number of columns in the sheet
            name: Name of the sheet
        """
        self.name = name
        self.n_rows = rows
        self.n_cols = cols
        
        # Create column headers (A, B, C, ..., AA, AB, ...)
        self.headers = [self._index_to_column(i) for i in range(cols)]
        
        # Initialize the DataFrame with None values
        # We use object dtype to allow mixed types (strings, numbers, etc.)
        self.df = pd.DataFrame(
            data=np.full((rows, cols), None, dtype=object),
            index=range(1, rows+1),  # 1-based row indices to match Excel
            columns=self.headers
        )
        
        # Dependencies between cells for recalculation (target -> {precedents})
        self.deps = defaultdict(set)
        
        # Reference to the parent workbook (set by the workbook when adding the sheet)
        self.workbook = None
        
        # Store formulas separately since DataFrame can't distinguish between
        # values and formulas
        self.formulas = {}  # {cell_ref: formula_string}
        
        # Cache for formula evaluation results
        self.formula_cache = {}  # {cell_ref: evaluated_result}
        
        # Track which cells are dirty (need recalculation)
        self.dirty_cells = set()
    
    def _index_to_column(self, index: int) -> str:
        """Convert a 0-based column index to Excel-style column name (A, B, C, ..., AA, AB, ...)"""
        result = ""
        while index >= 0:
            result = string.ascii_uppercase[index % 26] + result
            index = index // 26 - 1
        return result
    
    def _column_to_index(self, column: str) -> int:
        """Convert an Excel-style column name to 0-based index"""
        result = 0
        column = column.upper()  # Ensure uppercase for consistency
        for char in column:
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1
    
    def _split_ref(self, ref: str) -> Tuple[str, str]:
        """
        Split a cell reference that might include a sheet name.
        
        Args:
            ref: Cell reference which might be "A1" or "Sheet2!A1"
            
        Returns:
            Tuple of (sheet_name, cell_id)
        """
        if '!' in ref:
            sheet, cell = ref.split('!', 1)
            return sheet.upper(), cell.upper()
        return self.name.upper(), ref.upper()
    
    def _parse_cell_ref(self, cell_ref: str) -> Tuple[int, str]:
        """
        Parse a cell reference like 'A1' into row and column.
        
        Returns:
            Tuple of (row_index, col_name)
        """
        match = re.match(r'^([A-Za-z]+)(\d+)$', cell_ref)
        if not match:
            raise ValueError(f"Invalid cell reference format: {cell_ref}")
        
        col_str, row_str = match.groups()
        col_str = col_str.upper()  # Convert to uppercase for consistency
        row_index = int(row_str)  # Keep 1-based index for pandas
        
        return row_index, col_str
    
    def _parse_range_ref(self, range_ref: str) -> Tuple[int, str, int, str]:
        """
        Parse a range reference like 'A1:C3' into start and end coordinates.
        
        Returns:
            Tuple of (start_row, start_col, end_row, end_col)
        """
        cells = range_ref.split(':')
        if len(cells) != 2:
            raise ValueError(f"Invalid range reference: {range_ref}")
        
        start_row, start_col = self._parse_cell_ref(cells[0])
        end_row, end_col = self._parse_cell_ref(cells[1])
        
        return start_row, start_col, end_row, end_col
    
    def _register_dependencies(self, target_cell: str, formula: str) -> None:
        """
        Extract cell references from formula and register them as dependencies.
        
        Args:
            target_cell: The cell containing the formula
            formula: The formula to parse for dependencies
        """
        # Clear existing dependencies for this cell
        self.deps[target_cell] = set()
        
        # Find regular cell references
        for match in CELL_RE.finditer(formula):
            self.deps[target_cell].add(match.group(0).upper())
            
        # Find cross-sheet references
        for match in XREF_RE.finditer(formula):
            sheet_name, col, row = match.groups()
            self.deps[target_cell].add(f"{sheet_name.upper()}!{col.upper()}{row}")
    
    def get_cell(self, cell_ref: str, visited_cells=None) -> Any:
        """Get the value of a cell by its reference (e.g., 'A1' or 'Sheet2!A1')"""
        if visited_cells is None:
            visited_cells = set()
            
        # Check for circular references
        if cell_ref in visited_cells:
            return "#CIRC!"
        
        # Add this cell to visited set for circular reference detection
        visited_cells.add(cell_ref)
        
        # Handle cross-sheet references
        sheet_name, local_cell_ref = self._split_ref(cell_ref)
        
        if sheet_name != self.name.upper():
            # This is a cross-sheet reference
            if self.workbook:
                try:
                    other_sheet = self.workbook.sheet(sheet_name)
                    if not other_sheet:
                        return f"#REF!-{sheet_name}"
                    return other_sheet.get_cell(local_cell_ref, visited_cells.copy())
                except Exception as e:
                    print(f"Error getting cross-sheet reference: {e}")
                    return f"#REF!-{sheet_name}"
            else:
                return f"#WORKBOOK!"  # No workbook reference available
        
        # Handle local cell reference
        try:
            row_idx, col_name = self._parse_cell_ref(local_cell_ref)
            
            # Check if this is a formula cell
            if local_cell_ref.upper() in self.formulas:
                # Optimization: Check if formula result is cached and the cell is not dirty
                cache_key = local_cell_ref.upper()
                if cache_key in self.formula_cache and cache_key not in self.dirty_cells:
                    # Use cached result if available and not dirty
                    return self.formula_cache[cache_key]
                
                formula = self.formulas[local_cell_ref.upper()]
                
                # Use the formula engine to evaluate
                try:
                    from .formula_engine import evaluate_formula
                    result = evaluate_formula(formula, self, visited_cells.copy())
                    
                    # Cache the result for future use
                    self.formula_cache[cache_key] = result
                    
                    # Cell is no longer dirty after recalculation
                    self.dirty_cells.discard(cache_key)
                    
                    return result
                except ImportError:
                    # Fall back to simpler evaluation if formula_engine is not available
                    try:
                        # Simple hack for SUM
                        if formula.strip().upper().startswith('=SUM(') and formula.endswith(')'):
                            range_ref = formula.strip()[5:-1]  # Extract range between SUM( and )
                            values = self.get_range(range_ref)
                            result = sum(v for row in values for v in row if isinstance(v, (int, float)))
                            
                            # Cache the result
                            self.formula_cache[cache_key] = result
                            self.dirty_cells.discard(cache_key)
                            
                            return result
                        
                        # Other formulas not supported in fallback mode
                        return "#FORMULA!"
                    except Exception as e:
                        print(f"Error evaluating formula: {e}")
                        return "#ERROR!"
            
            # Check if the cell is within bounds
            if row_idx < 1 or row_idx > self.n_rows or col_name not in self.df.columns:
                return None  # Out of bounds
            
            # Return the cell value directly from DataFrame
            return self.df.at[row_idx, col_name]
            
        except Exception as e:
            print(f"Error accessing cell {local_cell_ref}: {e}")
            return f"#REF!-{local_cell_ref}"
    
    def set_cell(self, cell_ref: str, value: Any) -> None:
        """Set the value of a cell by its reference"""
        # Handle only local cell references for setting
        if '!' in cell_ref:
            raise ValueError("Cannot set cross-sheet cell directly")
            
        # Parse the cell reference
        try:
            row_idx, col_name = self._parse_cell_ref(cell_ref)
        except ValueError as e:
            raise ValueError(f"Invalid cell reference: {cell_ref}. {str(e)}")
            
        # Expand dataframe if needed
        self._ensure_cell_exists(row_idx, col_name)
        
        # Check if value is a formula
        if isinstance(value, str) and value.startswith('='):
            # Store the formula for later evaluation
            self.formulas[cell_ref.upper()] = value
            
            # Register dependencies for the formula
            self._register_dependencies(cell_ref.upper(), value)
            
            # Store a placeholder in the DataFrame 
            # The real value will be computed when get_cell is called
            self.df.at[row_idx, col_name] = "#FORMULA"
            
            # Mark this cell as dirty (needs recalculation)
            self.dirty_cells.add(cell_ref.upper())
            
            # Also invalidate cache for any cells that depend on this one
            self._mark_dependent_cells_dirty(cell_ref.upper())
        else:
            # If it was a formula before but isn't anymore, remove it
            if cell_ref.upper() in self.formulas:
                del self.formulas[cell_ref.upper()]
                
                # Remove from cache
                if cell_ref.upper() in self.formula_cache:
                    del self.formula_cache[cell_ref.upper()]
                
                # Mark dependent cells as dirty
                self._mark_dependent_cells_dirty(cell_ref.upper())
                
                # Also remove dependencies
                if cell_ref.upper() in self.deps:
                    del self.deps[cell_ref.upper()]
            
            # Store the literal value
            self.df.at[row_idx, col_name] = value
            
            # This cell is no longer dirty
            self.dirty_cells.discard(cell_ref.upper())
            
            # But cells that depend on it are now dirty
            self._mark_dependent_cells_dirty(cell_ref.upper())
        
        # If there's a workbook, trigger recalculation
        if self.workbook:
            self.workbook.recalculate()
    
    def _ensure_cell_exists(self, row_idx: int, col_name: str) -> None:
        """Ensure that the cell exists in the DataFrame, expanding it if needed"""
        # Add new rows if needed
        if row_idx > self.n_rows:
            new_rows = row_idx - self.n_rows
            new_df = pd.DataFrame(
                data=np.full((new_rows, len(self.df.columns)), None, dtype=object),
                index=range(self.n_rows + 1, row_idx + 1),
                columns=self.df.columns
            )
            self.df = pd.concat([self.df, new_df])
            self.n_rows = row_idx
        
        # Add new columns if needed
        if col_name not in self.df.columns:
            col_idx = self._column_to_index(col_name)
            
            # Generate missing columns
            missing_cols = []
            for i in range(len(self.df.columns), col_idx + 1):
                missing_cols.append(self._index_to_column(i))
            
            # Add the columns to the DataFrame
            for col in missing_cols:
                self.df[col] = None
                
            # Reorder columns alphabetically
            self.df = self.df.reindex(sorted(self.df.columns, key=lambda x: self._column_to_index(x)), axis=1)
            
            # Update headers and column count
            self.headers = list(self.df.columns)
            self.n_cols = len(self.headers)
    
    def get_range(self, range_ref: str) -> List[List[Any]]:
        """Get the values in a cell range (e.g., 'A1:C3')"""
        start_row, start_col, end_row, end_col = self._parse_range_ref(range_ref)
        
        # Get the numeric indices for columns
        start_col_idx = self._column_to_index(start_col)
        end_col_idx = self._column_to_index(end_col)
        
        # Construct column list
        col_list = [self._index_to_column(i) for i in range(start_col_idx, end_col_idx + 1)]
        
        # Ensure all cells in range exist
        self._ensure_cell_exists(end_row, end_col)
        
        # Extract the range as a DataFrame
        try:
            range_df = self.df.loc[start_row:end_row, col_list]
            
            # Convert to list of lists and evaluate any formulas
            result = []
            for _, row in range_df.iterrows():
                row_data = []
                for col, value in row.items():
                    cell_ref = f"{col}{_}"
                    if cell_ref.upper() in self.formulas:
                        # This is a formula cell, get its value
                        row_data.append(self.get_cell(cell_ref))
                    else:
                        row_data.append(value)
                result.append(row_data)
            
            return result
        except Exception as e:
            print(f"Error getting range {range_ref}: {e}")
            # Return empty data for out-of-bounds ranges
            return [[None for _ in range(end_col_idx - start_col_idx + 1)] 
                   for _ in range(end_row - start_row + 1)]
    
    def add_row(self, values: Optional[List[Any]] = None) -> None:
        """Add a new row at the bottom of the sheet"""
        self.n_rows += 1
        new_idx = self.n_rows
        
        # Create a new row with default values
        new_row = pd.Series(data=None, index=self.df.columns, dtype=object)
        
        # Fill in provided values
        if values:
            for col_idx, value in enumerate(values[:self.n_cols]):
                col_name = self.headers[col_idx]
                new_row[col_name] = value
        
        # Add the row to the DataFrame
        self.df.loc[new_idx] = new_row
    
    def add_column(self, name: Optional[str] = None, values: Optional[List[Any]] = None) -> None:
        """Add a new column to the right of the sheet"""
        # Generate column name if not provided
        if name is None:
            name = self._index_to_column(self.n_cols)
        
        # Add the new column
        self.df[name] = None
        self.headers.append(name)
        self.n_cols += 1
        
        # Fill in provided values
        if values:
            for row_idx, value in enumerate(values[:self.n_rows], 1):
                self.df.at[row_idx, name] = value
    
    def delete_row(self, index: int) -> None:
        """Delete a row by its index (1-based for consistency with DataFrame)"""
        if index < 1 or index > self.n_rows:
            raise ValueError(f"Row index out of bounds: {index}")
        
        # Drop the row
        self.df = self.df.drop(index)
        
        # Re-index the DataFrame to ensure continuous indices
        self.df = self.df.reset_index(drop=True)
        self.df.index = range(1, len(self.df) + 1)
        
        self.n_rows -= 1
    
    def delete_column(self, col_name_or_idx: Union[str, int]) -> None:
        """Delete a column by its name or index"""
        # Convert index to column name if needed
        if isinstance(col_name_or_idx, int):
            if col_name_or_idx < 0 or col_name_or_idx >= self.n_cols:
                raise ValueError(f"Column index out of bounds: {col_name_or_idx}")
            col_name = self.headers[col_name_or_idx]
        else:
            col_name = col_name_or_idx.upper()
            if col_name not in [h.upper() for h in self.headers]:
                raise ValueError(f"Column not found: {col_name}")
            # Find the exact case-matching header
            col_name = next(h for h in self.headers if h.upper() == col_name)
        
        # Drop the column
        self.df = self.df.drop(columns=col_name)
        
        # Update headers and column count
        self.headers = list(self.df.columns)
        self.n_cols = len(self.headers)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the spreadsheet to a dictionary representation"""
        # Convert DataFrame to nested list
        cells = self.df.fillna(None).values.tolist()
        
        return {
            "name": self.name,
            "rows": self.n_rows,
            "cols": self.n_cols,
            "headers": self.headers,
            "cells": cells
        }
    
    def optimized_to_dict(self, max_rows=None, max_cols=None) -> Dict[str, Any]:
        """
        Convert the spreadsheet to a more efficient dictionary representation.
        Limits the size of the returned data.
        """
        # Determine rows and columns to include
        rows_to_include = min(self.n_rows, max_rows) if max_rows is not None else self.n_rows
        cols_to_include = min(self.n_cols, max_cols) if max_cols is not None else self.n_cols
        
        # Get subset of headers
        trimmed_headers = self.headers[:cols_to_include]
        
        # Get subset of cells
        if rows_to_include < self.n_rows or cols_to_include < self.n_cols:
            # Only select the required subset
            subset_df = self.df.iloc[:rows_to_include, :cols_to_include]
            trimmed_cells = subset_df.fillna(None).values.tolist()
        else:
            # Use the full dataframe
            trimmed_cells = self.df.fillna(None).values.tolist()
        
        return {
            "name": self.name,
            "rows": self.n_rows,  # Keep original dimensions
            "cols": self.n_cols,  # Keep original dimensions
            "headers": trimmed_headers,
            "cells": trimmed_cells,
            "trimmed": {
                "rows": rows_to_include,
                "cols": cols_to_include
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataFrameSpreadsheet':
        """Create a spreadsheet from a dictionary representation"""
        # Extract dimensions and headers
        rows = data.get("rows", 100)
        cols = data.get("cols", 30) 
        name = data.get("name", "Sheet1")
        headers = data.get("headers", [])
        
        # Create the spreadsheet
        sheet = cls(rows=rows, cols=cols, name=name)
        
        # If there are cells data, populate the DataFrame
        cells = data.get("cells", [])
        if cells:
            # Create DataFrame from cells
            df = pd.DataFrame(cells)
            
            # Set column names if available
            if headers and len(headers) == df.shape[1]:
                df.columns = headers
            
            # Set index to 1-based
            df.index = range(1, len(df) + 1)
            
            # Assign to spreadsheet
            sheet.df = df
        
        return sheet
    
    def from_original_model(self, original_sheet) -> 'DataFrameSpreadsheet':
        """
        Convert from the original list-based model to DataFrame model
        
        Args:
            original_sheet: The original Spreadsheet instance
            
        Returns:
            Self, with data copied from original sheet
        """
        # Copy basic properties
        self.name = original_sheet.name
        self.n_rows = original_sheet.n_rows
        self.n_cols = original_sheet.n_cols
        self.headers = original_sheet.headers.copy()
        self.deps = original_sheet.deps.copy()
        self.workbook = original_sheet.workbook
        
        # Initialize DataFrame with the correct dimensions
        self.df = pd.DataFrame(
            data=np.full((self.n_rows, self.n_cols), None, dtype=object),
            index=range(1, self.n_rows+1),
            columns=self.headers
        )
        
        # Copy cell data
        for row_idx, row in enumerate(original_sheet.cells):
            for col_idx, value in enumerate(row):
                if value is not None:
                    df_row = row_idx + 1  # Convert to 1-based index
                    df_col = self.headers[col_idx]
                    
                    # Check if it's a formula
                    if isinstance(value, str) and value.startswith('='):
                        self.formulas[f"{df_col}{df_row}".upper()] = value
                        self.df.at[df_row, df_col] = "#FORMULA"
                    else:
                        self.df.at[df_row, df_col] = value
        
        return self
    
    def to_original_model(self, target_sheet) -> None:
        """
        Convert from DataFrame model back to original list-based model
        
        Args:
            target_sheet: The target original Spreadsheet instance to update
        """
        # Copy basic properties
        target_sheet.name = self.name
        target_sheet.n_rows = self.n_rows
        target_sheet.n_cols = self.n_cols
        target_sheet.headers = self.headers.copy()
        target_sheet.deps = self.deps.copy()
        target_sheet.workbook = self.workbook
        
        # Initialize cells with None
        target_sheet.cells = [[None for _ in range(self.n_cols)] for _ in range(self.n_rows)]
        
        # Copy values from DataFrame to cells
        for row_idx in range(1, self.n_rows + 1):
            for col_idx, col_name in enumerate(self.headers):
                cell_ref = f"{col_name}{row_idx}"
                
                # If it's a formula, get it from formulas dict
                if cell_ref.upper() in self.formulas:
                    value = self.formulas[cell_ref.upper()]
                else:
                    value = self.df.at[row_idx, col_name]
                
                # Apply to original model (0-based index)
                if row_idx - 1 < len(target_sheet.cells) and col_idx < len(target_sheet.cells[0]):
                    target_sheet.cells[row_idx - 1][col_idx] = value 
    
    def _mark_dependent_cells_dirty(self, cell_ref: str) -> None:
        """Mark all cells that depend on this one as dirty for invalidating cache."""
        # Find all cells that directly or indirectly depend on this cell
        # (need to search in forward dependency direction)
        queue = [cell_ref.upper()]
        visited = set()
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
                
            visited.add(current)
            
            # Find cells that depend on the current cell
            dependent_cells = set()
            for target, deps in self.deps.items():
                if current in deps:
                    dependent_cells.add(target)
            
            # Mark them dirty and add to queue
            for dep in dependent_cells:
                self.dirty_cells.add(dep)
                # Remove from cache since they need recalculation
                if dep in self.formula_cache:
                    del self.formula_cache[dep]
                queue.append(dep) 