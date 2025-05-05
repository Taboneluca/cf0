from typing import List, Dict, Any, Optional, Union, Tuple, Set, DefaultDict
import re
import string
import ast, operator
from collections import defaultdict

# Add constants at the top of the file, before the Spreadsheet class
DEFAULT_ROWS = 100
DEFAULT_COLS = 30

# Cell reference patterns
CELL_RE = re.compile(r"([A-Za-z]+)(\d+)", re.I)  # Matches A1, b2, etc.
XREF_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)!([A-Za-z]+)(\d+)", re.I)  # Matches Sheet2!A1, etc.

class Spreadsheet:
    _SAFE_OPS = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg, ast.Pow: operator.pow,
    }

    def _eval_expr(self, node):
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._SAFE_OPS:
            return self._SAFE_OPS[type(node.op)](self._eval_expr(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in self._SAFE_OPS:
            return self._SAFE_OPS[type(node.op)](
                self._eval_expr(node.left), self._eval_expr(node.right))
        if isinstance(node, ast.Name):
            value = self.get_cell(node.id)
            return value if isinstance(value, (int, float)) else 0
        raise ValueError("Unsafe formula")

    def _evaluate_formula(self, formula: str, visited_cells=None):
        """
        Evaluate a formula, handling cell references and basic operations.
        Uses visited_cells to detect circular references.
        """
        if visited_cells is None:
            visited_cells = set()
        
        # Support very simple Excel-style functions before falling back to AST.
        upper_formula = formula.strip().upper()
        if upper_formula.startswith('=SUM(') and upper_formula.endswith(')'):
            args_part = formula.strip()[5:-1]  # drop leading '=SUM(' and trailing ')'
            args = [a.strip() for a in args_part.split(',') if a.strip()]
            total = 0
            for arg in args:
                try:
                    if ':' in arg:
                        for row in self.get_range(arg):
                            for cell in row:
                                if isinstance(cell, (int, float)):
                                    total += cell
                    else:
                        val = self.get_cell(arg, visited_cells)
                        if isinstance(val, (int, float)):
                            total += val
                except Exception as e:
                    print(f"Error in SUM formula: {e}")
                    pass
            return total
            
        # Handle cell references in formulas like =A1+B2
        processed_formula = formula.lstrip('=')
        
        # Replace cell references with their values
        def replace_cell_ref(match):
            cell_ref = match.group(0)
            # Check for circular reference
            if cell_ref in visited_cells:
                return "#CIRC!"
                
            try:
                value = self.get_cell(cell_ref, visited_cells)
                # Return numeric value or 0 if not numeric
                if isinstance(value, (int, float)):
                    return str(value)
                else:
                    return "0"
            except Exception as e:
                print(f"Error getting cell value for {cell_ref}: {e}")
                return "0"  # Default to 0 on error
                
        # Replace cross-sheet references first
        for match in XREF_RE.finditer(processed_formula):
            sheet_name, col, row = match.groups()
            ref = f"{sheet_name}!{col}{row}"
            try:
                # No need to import get_workbook here - use workbook reference
                # from workbook_store import get_workbook  # Import here to avoid circular import
                # Try to get the workbook and sheet from the cross-reference
                # This is handled by the _split_ref method and the parent workbook
                value = self.get_cell(ref, visited_cells)
                processed_formula = processed_formula.replace(ref, str(value) if isinstance(value, (int, float)) else "0")
            except Exception as e:
                print(f"Error with cross-sheet reference {ref}: {e}")
                processed_formula = processed_formula.replace(ref, "0")
        
        # Replace regular cell references
        processed_formula = CELL_RE.sub(replace_cell_ref, processed_formula)
        
        # Strip the leading '=' and try AST evaluation
        try:
            tree = ast.parse(processed_formula, mode='eval')
            return self._eval_expr(tree.body)
        except Exception as e:
            print(f"Formula evaluation error: {e} for formula: {formula}")
            return "#ERROR!"  # Return error indicator

    def __init__(self, rows: int = DEFAULT_ROWS, cols: int = DEFAULT_COLS, name: str = "Sheet1"):
        """
        Initialize a new spreadsheet with the given dimensions.
        
        Args:
            rows: Number of rows in the sheet
            cols: Number of columns in the sheet
            name: Name of the sheet
        """
        self.name = name
        self.n_rows = rows
        self.n_cols = cols
        # Initialize with empty cells
        self.cells: List[List[Any]] = [[None for _ in range(cols)] for _ in range(rows)]
        # Headers (column names) - optional
        self.headers: List[str] = [self._index_to_column(i) for i in range(cols)]
        # Dependencies between cells for recalculation
        self.deps: DefaultDict[str, Set[str]] = defaultdict(set)  # target -> {precedents}
        # Reference to the parent workbook (set by the workbook when adding the sheet)
        self.workbook = None
    
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
    
    def _parse_cell_ref(self, cell_ref: str) -> Tuple[int, int]:
        """
        Parse a cell reference like 'A1' into row and column indices.
        Case-insensitive: 'a1' and 'A1' will be treated the same.
        
        Returns:
            Tuple of (row_index, col_index) as 0-based indices
        """
        match = re.match(r'^([A-Za-z]+)(\d+)$', cell_ref)
        if not match:
            # Check if it's potentially a cross-sheet reference that was passed incorrectly
            if '!' in cell_ref:
                sheet, local_ref = cell_ref.split('!', 1)
                if re.match(r'^([A-Za-z]+)(\d+)$', local_ref):
                    raise ValueError(f"Invalid cell reference format: {cell_ref}. Use sheet.get_cell('{cell_ref}') for cross-sheet references.")
            raise ValueError(f"Invalid cell reference format: {cell_ref}. Expected format like 'A1', got '{cell_ref}'")
        
        col_str, row_str = match.groups()
        col_str = col_str.upper()  # Convert to uppercase for consistency
        col_index = self._column_to_index(col_str)
        row_index = int(row_str) - 1  # Convert to 0-based index
        
        return row_index, col_index
    
    def _parse_range_ref(self, range_ref: str) -> Tuple[int, int, int, int]:
        """
        Parse a range reference like 'A1:C3' into start and end coordinates.
        
        Returns:
            Tuple of (start_row, start_col, end_row, end_col) as 0-based indices
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
        
        # Special case for dummy sheets created for missing references
        if self.name.startswith("_MISSING_"):
            return f"#REF!-{sheet_name}"
            
        if sheet_name != self.name.upper():
            # This is a cross-sheet reference
            if self.workbook:
                try:
                    other_sheet = self.workbook.sheet(sheet_name)
                    if not other_sheet:
                        print(f"Sheet '{sheet_name}' not found in workbook")
                        return f"#REF!-{sheet_name}"
                    return other_sheet.get_cell(local_cell_ref, visited_cells.copy())
                except Exception as e:
                    print(f"Error getting cross-sheet reference: {e}")
                    return f"#REF!-{sheet_name}"
            else:
                return f"#WORKBOOK!"  # No workbook reference available
                
        # Handle local cell reference
        try:
            row, col = self._parse_cell_ref(local_cell_ref)
            
            if row < 0 or row >= self.n_rows or col < 0 or col >= self.n_cols:
                return f"#REF!-{local_cell_ref}"  # Out of bounds
            
            value = self.cells[row][col]
            if isinstance(value, str) and value.startswith('=') and len(value.strip()) > 1:
                try:
                    # Pass the visited cells to detect circular references
                    return self._evaluate_formula(value, visited_cells.copy())
                except Exception as e:
                    print(f"Formula evaluation error: {e}")
                    return f"#ERROR!-{local_cell_ref}"
            return value
        except Exception as e:
            print(f"Error accessing cell {local_cell_ref}: {e}")
            return f"#REF!-{local_cell_ref}"
    
    def set_cell(self, cell_ref: str, value: Any) -> None:
        """Set the value of a cell by its reference"""
        # Handle only local cell references for setting
        if '!' in cell_ref:
            raise ValueError("Cannot set cross-sheet cell directly")
        
        # Reject lone "=" to prevent unnecessary formula processing
        if isinstance(value, str) and value.strip() == "=":
            # treat as empty entry, do *not* save single "="
            value = ""
        
        row, col = self._parse_cell_ref(cell_ref)
        
        if row < 0 or row >= self.n_rows or col < 0 or col >= self.n_cols:
            raise ValueError(f"Cell reference out of bounds: {cell_ref}")
        
        # Register dependencies if this is a formula
        if isinstance(value, str) and value.startswith('='):
            self._register_dependencies(cell_ref.upper(), value)
        else:
            # If this was a formula before but isn't anymore, clear its dependencies
            if cell_ref.upper() in self.deps:
                self.deps.pop(cell_ref.upper())
        
        # Store the value
        self.cells[row][col] = value
        
        # If there's a workbook, trigger recalculation and save
        if self.workbook:
            # Save changes to persistent storage if workbook is present
            try:
                # Defer import to avoid circular import
                # Persistence will happen through workbook_store's get_sheet
                pass
            except ImportError:
                # Optional dependency - skip if not available
                pass
                
            self.workbook.recalculate()
    
    def get_range(self, range_ref: str) -> List[List[Any]]:
        """Get the values in a cell range (e.g., 'A1:C3')"""
        start_row, start_col, end_row, end_col = self._parse_range_ref(range_ref)
        
        if (start_row < 0 or end_row >= self.n_rows or 
            start_col < 0 or end_col >= self.n_cols):
            raise ValueError(f"Range reference out of bounds: {range_ref}")
        
        result = []
        for row in range(start_row, end_row + 1):
            row_data = []
            for col in range(start_col, end_col + 1):
                row_data.append(self.cells[row][col])
            result.append(row_data)
        
        return result
    
    def add_row(self, values: Optional[List[Any]] = None) -> None:
        """Add a new row at the bottom of the sheet"""
        if values is None:
            values = [None] * self.n_cols
        
        # Pad or truncate values to match column count
        if len(values) < self.n_cols:
            values = values + [None] * (self.n_cols - len(values))
        elif len(values) > self.n_cols:
            values = values[:self.n_cols]
        
        self.cells.append(values)
        self.n_rows += 1
    
    def add_column(self, name: Optional[str] = None, values: Optional[List[Any]] = None) -> None:
        """Add a new column to the right of the sheet"""
        # Generate column name if not provided
        if name is None:
            name = self._index_to_column(self.n_cols)
        
        self.headers.append(name)
        
        # Add a new cell to each row
        if values is None:
            values = [None] * self.n_rows
        
        # Pad or truncate values to match row count
        if len(values) < self.n_rows:
            values = values + [None] * (self.n_rows - len(values))
        elif len(values) > self.n_rows:
            values = values[:self.n_rows]
        
        for row_idx, value in enumerate(values):
            self.cells[row_idx].append(value)
        
        self.n_cols += 1
    
    def delete_row(self, index: int) -> None:
        """Delete a row by its index (0-based)"""
        if index < 0 or index >= self.n_rows:
            raise ValueError(f"Row index out of bounds: {index}")
        
        self.cells.pop(index)
        self.n_rows -= 1
    
    def delete_column(self, index: int) -> None:
        """Delete a column by its index (0-based)"""
        if index < 0 or index >= self.n_cols:
            raise ValueError(f"Column index out of bounds: {index}")
        
        self.headers.pop(index)
        
        for row in self.cells:
            row.pop(index)
        
        self.n_cols -= 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the spreadsheet to a dictionary representation"""
        return {
            "name": self.name,
            "headers": self.headers,
            "rows": self.n_rows,
            "columns": self.n_cols,
            "cells": self.cells
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Spreadsheet':
        """Create a spreadsheet from a dictionary representation"""
        sheet = cls(rows=data["rows"], cols=data["columns"], name=data["name"])
        sheet.headers = data["headers"]
        sheet.cells = data["cells"]
        return sheet

# Remove old/deprecated code
# current_sheet = Spreadsheet()
sheets: dict[str, Spreadsheet] = {}

# Removing old/deprecated function
# def get_sheet(sid: str):
#     """
#     Get or create a spreadsheet for a session
#     
#     Args:
#         sid: The session ID
#         
#     Returns:
#         The spreadsheet for the session
#     """
#     if sid not in sheets:
#         sheets[sid] = Spreadsheet()
#     return sheets[sid] 