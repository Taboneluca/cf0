"""
Excel-parity Formula Engine

This module provides an engine for evaluating Excel-style formulas with high compatibility.
It supports all basic operations, functions like SUM, AVERAGE, etc.,
and properly handles cell references and ranges.
"""

import re
import operator
import math
import statistics
from typing import Any, Dict, List, Set, Tuple, Union, Callable
import numpy as np

# Cell reference patterns
CELL_RE = re.compile(r"([A-Za-z]+)(\d+)", re.I)  # Matches A1, b2, etc.
XREF_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)!([A-Za-z]+)(\d+)", re.I)  # Matches Sheet2!A1
RANGE_RE = re.compile(r"([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)", re.I)  # Matches A1:B10
XRANGE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)!([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)", re.I)  # Sheet1!A1:B10

# Function pattern
FUNCTION_RE = re.compile(r"([A-Za-z]+)\((.*)\)", re.I)  # Matches SUM(...), COUNT(...), etc.

# Define available functions with their implementations
EXCEL_FUNCTIONS = {
    "SUM": lambda args: sum(arg for arg in args if isinstance(arg, (int, float))),
    "AVERAGE": lambda args: statistics.mean([arg for arg in args if isinstance(arg, (int, float))]) if args else 0,
    "COUNT": lambda args: sum(1 for arg in args if arg is not None),
    "COUNTA": lambda args: sum(1 for arg in args if arg is not None and arg != ""),
    "MAX": lambda args: max([arg for arg in args if isinstance(arg, (int, float))]) if args else 0,
    "MIN": lambda args: min([arg for arg in args if isinstance(arg, (int, float))]) if args else 0,
    "IF": lambda args: args[1] if args[0] else args[2] if len(args) > 2 else False,
    "ROUND": lambda args: round(args[0], args[1]) if len(args) > 1 else round(args[0]),
    "ABS": lambda args: abs(args[0]) if isinstance(args[0], (int, float)) else args[0],
    "FLOOR": lambda args: math.floor(args[0]) if isinstance(args[0], (int, float)) else args[0],
    "CEILING": lambda args: math.ceil(args[0]) if isinstance(args[0], (int, float)) else args[0],
    "CONCATENATE": lambda args: "".join(str(arg) for arg in args),
    "LEN": lambda args: len(str(args[0])) if args else 0,
    "UPPER": lambda args: str(args[0]).upper() if args else "",
    "LOWER": lambda args: str(args[0]).lower() if args else "",
    "TRIM": lambda args: str(args[0]).strip() if args else "",
    "LEFT": lambda args: str(args[0])[:args[1]] if len(args) > 1 else str(args[0])[:1] if args else "",
    "RIGHT": lambda args: str(args[0])[-args[1]:] if len(args) > 1 else str(args[0])[-1:] if args else "",
    "MID": lambda args: str(args[0])[args[1]-1:args[1]-1+args[2]] if len(args) > 2 else "",
    "SUBSTITUTE": lambda args: str(args[0]).replace(str(args[1]), str(args[2])) if len(args) > 2 else str(args[0]),
    "PROPER": lambda args: str(args[0]).title() if args else "",
    "TEXT": lambda args: str(args[0]) if args else "",  # Simplified, doesn't handle format
    "VALUE": lambda args: float(args[0]) if args and isinstance(args[0], str) and args[0].replace('.', '', 1).isdigit() else 0,
    "SUMIF": lambda args: sum(args[1][i] for i, x in enumerate(args[0]) if x == args[2]) if len(args) > 2 else 0,
    "COUNTIF": lambda args: sum(1 for x in args[0] if x == args[1]) if len(args) > 1 else 0,
    "AVERAGEIF": lambda args: statistics.mean([args[1][i] for i, x in enumerate(args[0]) if x == args[2]]) if len(args) > 2 and any(x == args[2] for x in args[0]) else 0,
    "AND": lambda args: all(bool(arg) for arg in args),
    "OR": lambda args: any(bool(arg) for arg in args),
    "NOT": lambda args: not bool(args[0]) if args else True,
    "TRUE": lambda args: True,
    "FALSE": lambda args: False,
    "PI": lambda args: math.pi,
    "NOW": lambda args: "NOW_PLACEHOLDER",  # Would be datetime.now() in real implementation
    "TODAY": lambda args: "TODAY_PLACEHOLDER",  # Would be datetime.now().date() in real implementation
    "RAND": lambda args: np.random.random(),
    "INT": lambda args: int(args[0]) if isinstance(args[0], (int, float)) else 0,
    "PRODUCT": lambda args: np.prod([arg for arg in args if isinstance(arg, (int, float))]) if args else 0,
    "POWER": lambda args: math.pow(args[0], args[1]) if len(args) > 1 and isinstance(args[0], (int, float)) and isinstance(args[1], (int, float)) else 0,
    "SQRT": lambda args: math.sqrt(args[0]) if isinstance(args[0], (int, float)) and args[0] >= 0 else "#ERROR!",
    "LN": lambda args: math.log(args[0]) if isinstance(args[0], (int, float)) and args[0] > 0 else "#ERROR!",
    "LOG10": lambda args: math.log10(args[0]) if isinstance(args[0], (int, float)) and args[0] > 0 else "#ERROR!",
    "EXP": lambda args: math.exp(args[0]) if isinstance(args[0], (int, float)) else "#ERROR!",
    "SIN": lambda args: math.sin(args[0]) if isinstance(args[0], (int, float)) else "#ERROR!",
    "COS": lambda args: math.cos(args[0]) if isinstance(args[0], (int, float)) else "#ERROR!",
    "TAN": lambda args: math.tan(args[0]) if isinstance(args[0], (int, float)) else "#ERROR!",
}

# Binary operators and their implementations
OPERATORS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "^": operator.pow,
    "=": operator.eq,
    "<>": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "&": lambda a, b: str(a) + str(b),  # String concatenation
}

def tokenize_formula(formula: str) -> List[str]:
    """
    Convert a formula string into tokens for parsing.
    
    Args:
        formula: The formula string (with or without leading =)
        
    Returns:
        List of tokens
    """
    # Remove leading equals sign if present
    formula = formula.lstrip('=')
    
    # Add spaces around operators and parentheses for easier splitting
    for op in ["(", ")", "+", "-", "*", "/", "^", "=", "<>", ">", "<", ">=", "<=", "&", ","]:
        formula = formula.replace(op, f" {op} ")
    
    # Handle special case of negative numbers vs. subtraction
    # This is a simple approach and may need refinement
    tokens = []
    for token in formula.split():
        if token:  # Skip empty tokens
            tokens.append(token)
    
    return tokens

def evaluate_formula(formula: str, sheet, visited_cells=None) -> Any:
    """
    Evaluate an Excel-style formula within the context of a sheet.
    
    Args:
        formula: The formula string (with or without leading =)
        sheet: The spreadsheet object that contains the formula
        visited_cells: Set of already visited cells (for circular reference detection)
        
    Returns:
        The evaluated result
    """
    if visited_cells is None:
        visited_cells = set()
    
    # Validate input
    if not isinstance(formula, str):
        return formula
    
    # Remove leading equals sign if present
    formula = formula.lstrip('=')
    
    # Check if this is a simple function call like SUM(A1:A10)
    function_match = FUNCTION_RE.match(formula)
    if function_match:
        func_name = function_match.group(1).upper()
        args_str = function_match.group(2).strip()
        
        # If function exists in our dictionary
        if func_name in EXCEL_FUNCTIONS:
            # Parse arguments
            args = parse_function_args(args_str, sheet, visited_cells)
            
            # Call the function
            try:
                return EXCEL_FUNCTIONS[func_name](args)
            except Exception as e:
                print(f"Error evaluating function {func_name}: {e}")
                return "#ERROR!"
    
    # Otherwise, replace cell references and evaluate as expression
    try:
        # Replace cell references with their values
        tokens = tokenize_formula(formula)
        result = parse_expression(tokens, sheet, visited_cells)
        return result
    except Exception as e:
        print(f"Error evaluating formula: {e}")
        return "#ERROR!"

def parse_function_args(args_str: str, sheet, visited_cells: Set[str]) -> List[Any]:
    """
    Parse function arguments, which may include cell references, ranges, or literals.
    
    Args:
        args_str: The function arguments string
        sheet: The spreadsheet object
        visited_cells: Set of already visited cells
        
    Returns:
        List of argument values
    """
    if not args_str:
        return []
    
    # Split args at commas, but respect parentheses (for nested functions)
    args = []
    current_arg = ""
    paren_level = 0
    
    for char in args_str:
        if char == ',' and paren_level == 0:
            args.append(current_arg.strip())
            current_arg = ""
        else:
            if char == '(':
                paren_level += 1
            elif char == ')':
                paren_level -= 1
            current_arg += char
    
    if current_arg:
        args.append(current_arg.strip())
    
    # Process each argument
    parsed_args = []
    for arg in args:
        # Check if it's a range reference
        range_match = RANGE_RE.fullmatch(arg)
        xrange_match = XRANGE_RE.fullmatch(arg)
        
        if range_match or xrange_match:
            # It's a range reference, get values as a flat list
            values = []
            try:
                # We need to access the private method directly due to different return format
                # This is a bit of a hack but necessary for now
                range_values = sheet.get_range(arg)
                values = [cell for row in range_values for cell in row]
            except Exception as e:
                print(f"Error getting range {arg}: {e}")
            parsed_args.append(values)
        
        # Check if it's a cell reference
        elif CELL_RE.fullmatch(arg) or XREF_RE.fullmatch(arg):
            # It's a cell reference
            value = sheet.get_cell(arg, visited_cells.copy())
            parsed_args.append(value)
        
        # Check if it's a nested function
        elif FUNCTION_RE.match(arg):
            # It's a nested function
            value = evaluate_formula(arg, sheet, visited_cells.copy())
            parsed_args.append(value)
        
        # Otherwise, it's a literal
        else:
            # Try to convert to number if possible
            try:
                # Check if it's a string literal (enclosed in quotes)
                if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
                    parsed_args.append(arg[1:-1])  # Remove quotes
                else:
                    # Try to convert to number
                    parsed_args.append(float(arg) if '.' in arg else int(arg))
            except ValueError:
                # Not a number, treat as string
                parsed_args.append(arg)
    
    return parsed_args

def parse_expression(tokens: List[str], sheet, visited_cells: Set[str]) -> Any:
    """
    Parse and evaluate an expression with precedence rules.
    
    Args:
        tokens: List of tokens from tokenize_formula
        sheet: The spreadsheet object
        visited_cells: Set of already visited cells
        
    Returns:
        The evaluated result
    """
    # Convert cell references to their values
    processed_tokens = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        
        # Check if it's a cell reference
        cell_match = CELL_RE.fullmatch(token)
        xcell_match = XREF_RE.fullmatch(token)
        
        if cell_match or xcell_match:
            # It's a cell reference
            value = sheet.get_cell(token, visited_cells.copy())
            # Convert to number if possible
            if isinstance(value, (int, float)):
                processed_tokens.append(value)
            else:
                # Non-numeric values in formulas
                if value is None:
                    processed_tokens.append(0)  # Excel treats empty cells as 0 in formulas
                else:
                    processed_tokens.append(value)  # Could be string, boolean, etc.
        
        # Check if it's a range reference (should be in function args, not here)
        elif RANGE_RE.fullmatch(token) or XRANGE_RE.fullmatch(token):
            # Not expecting range references here
            processed_tokens.append("#REF!")
        
        # Check if it's a literal number
        elif token.replace('.', '', 1).replace('-', '', 1).isdigit():
            # It's a number
            processed_tokens.append(float(token) if '.' in token else int(token))
        
        # Check if it's a string literal
        elif (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
            # It's a string literal
            processed_tokens.append(token[1:-1])  # Remove quotes
        
        # Check if it's a function
        elif i + 1 < len(tokens) and tokens[i + 1] == "(":
            func_name = token.upper()
            # Find the closing parenthesis
            paren_level = 0
            j = i + 1
            func_tokens = []
            
            while j < len(tokens):
                if tokens[j] == "(":
                    paren_level += 1
                elif tokens[j] == ")":
                    paren_level -= 1
                    if paren_level == 0:
                        break
                func_tokens.append(tokens[j])
                j += 1
            
            # Extract function arguments
            func_args_str = " ".join(func_tokens[1:-1])  # Exclude opening/closing parentheses
            args = parse_function_args(func_args_str, sheet, visited_cells)
            
            # Call the function
            if func_name in EXCEL_FUNCTIONS:
                try:
                    value = EXCEL_FUNCTIONS[func_name](args)
                    processed_tokens.append(value)
                except Exception as e:
                    print(f"Error calling function {func_name}: {e}")
                    processed_tokens.append("#ERROR!")
            else:
                processed_tokens.append("#NAME?")
            
            i = j  # Skip processed tokens
        
        else:
            # Operator or other token
            processed_tokens.append(token)
        
        i += 1
    
    # Now evaluate the expression with operator precedence
    # This is a simplified version - a real implementation would handle more complexity
    # Convert infix to postfix, then evaluate
    
    result = 0
    operator_stack = []
    output_queue = []
    
    # Define precedence
    precedence = {
        "^": 4,
        "*": 3,
        "/": 3,
        "+": 2,
        "-": 2,
        "=": 1,
        "<>": 1,
        ">": 1,
        "<": 1,
        ">=": 1,
        "<=": 1,
        "&": 1
    }
    
    # Convert infix to postfix (Shunting-yard algorithm)
    for token in processed_tokens:
        if token in OPERATORS:
            # Operator
            while (operator_stack and operator_stack[-1] != "(" and 
                   precedence.get(operator_stack[-1], 0) >= precedence.get(token, 0)):
                output_queue.append(operator_stack.pop())
            operator_stack.append(token)
        elif token == "(":
            operator_stack.append(token)
        elif token == ")":
            while operator_stack and operator_stack[-1] != "(":
                output_queue.append(operator_stack.pop())
            if operator_stack and operator_stack[-1] == "(":
                operator_stack.pop()  # Discard the opening parenthesis
        else:
            # Operand
            output_queue.append(token)
    
    # Pop any remaining operators
    while operator_stack:
        output_queue.append(operator_stack.pop())
    
    # Evaluate postfix expression
    eval_stack = []
    for token in output_queue:
        if token in OPERATORS:
            # Operator
            if len(eval_stack) < 2:
                return "#ERROR!"
            b = eval_stack.pop()
            a = eval_stack.pop()
            try:
                result = OPERATORS[token](a, b)
                eval_stack.append(result)
            except Exception as e:
                print(f"Error applying operator {token}: {e}")
                return "#ERROR!"
        else:
            # Operand
            eval_stack.append(token)
    
    # The result should be the only item on the stack
    if len(eval_stack) == 1:
        return eval_stack[0]
    else:
        return "#ERROR!"

def extract_dependencies(formula: str) -> Set[str]:
    """
    Extract cell references from a formula to build dependency graph.
    
    Args:
        formula: The formula string (with or without leading =)
        
    Returns:
        Set of cell references found in the formula
    """
    dependencies = set()
    formula = formula.lstrip('=')
    
    # Find all standard cell references (A1, B2, etc.)
    for match in CELL_RE.finditer(formula):
        dependencies.add(match.group(0).upper())
    
    # Find all cross-sheet references (Sheet1!A1, etc.)
    for match in XREF_RE.finditer(formula):
        sheet_name, col, row = match.groups()
        dependencies.add(f"{sheet_name.upper()}!{col.upper()}{row}")
    
    # Find all range references (A1:B2, etc.) and add individual cells
    for match in RANGE_RE.finditer(formula):
        start_col, start_row, end_col, end_row = match.groups()
        # Add all cells in the range
        # Note: This is a simplified approach - a real implementation would generate all cells in the range
        dependencies.add(f"{start_col.upper()}{start_row}")
        dependencies.add(f"{end_col.upper()}{end_row}")
    
    # Find all cross-sheet range references (Sheet1!A1:B2, etc.)
    for match in XRANGE_RE.finditer(formula):
        sheet_name, start_col, start_row, end_col, end_row = match.groups()
        # Add the range boundaries
        dependencies.add(f"{sheet_name.upper()}!{start_col.upper()}{start_row}")
        dependencies.add(f"{sheet_name.upper()}!{end_col.upper()}{end_row}")
    
    return dependencies 