import asyncio
from typing import Dict, Any, Optional
from functools import partial
import json  # for serializing sheet state

from agents.ask_agent import AskAgent
from agents.analyst_agent import AnalystAgent
from spreadsheet_engine.model import Spreadsheet
from workbook_store import get_sheet, get_workbook
from chat.memory import get_history, add_to_history
from spreadsheet_engine.summary import sheet_summary

async def process_message(
    mode: str, 
    message: str, 
    wid: str, 
    sid: str, 
    sheet=None, 
    workbook_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a message by routing it to the appropriate agent.
    
    Args:
        mode: The agent mode ("ask" or "analyst")
        message: The user message to process
        wid: Workbook ID
        sid: Sheet ID in the workbook
        sheet: The spreadsheet to use (if None, uses get_sheet(wid, sid))
        workbook_metadata: Additional metadata about the workbook and its sheets
        
    Returns:
        Dict with reply, sheet state, and log of updates
    """
    # Use conversation history keyed by workbook ID only, not the sheet ID
    history_key = wid
    history = get_history(history_key)
    
    # Get the sheet if not provided
    if sheet is None:
        sheet = get_sheet(wid, sid)
    
    # Get the workbook
    workbook = get_workbook(wid)
    
    # Create workbook metadata if not provided
    if workbook_metadata is None:
        all_sheets_data = {name: s.to_dict() for name, s in workbook.all_sheets().items()}
        workbook_metadata = {
            "sheets": workbook.list_sheets(),
            "active": sid,
            "all_sheets_data": all_sheets_data
        }
    
    # Inject current workbook/sheet info into history for LLM context
    summary = sheet_summary(sheet=sheet)
    system_context = (
        f"Workbook: {wid}\nCurrent sheet: {sid}\n"
        f"Available sheets: {', '.join(workbook_metadata['sheets'])}\n"
        f"Sheet summary: {json.dumps(summary)}\n"
        "Call get_range if you need more detail."
    )
    
    history.insert(0, {
        "role": "system", 
        "content": system_context
    })
    
    # Create partial functions for all tools with the sheet parameter
    from spreadsheet_engine.operations import (
        get_cell, get_range, summarize_sheet, calculate,
        set_cell, add_row, add_column, delete_row, delete_column,
        sort_range, find_replace, create_new_sheet,
        get_row_by_header, get_column_by_header,
        apply_scalar_to_row, apply_scalar_to_column, set_cells,
        list_sheets, get_sheet_summary
    )
    
    # Helper wrapper functions to accept multiple parameter naming styles
    def _wrap_get_cell(get_cell_fn, sheet):
        """accept both `cell` and `cell_ref` so the agent never 500s"""
        def _f(cell_ref: str = None, cell: str = None, **kw):
            ref = cell_ref or cell
            if ref is None:
                return {"error": "Missing cell reference"}
            return get_cell_fn(ref, sheet=sheet)
        return _f
    
    def _wrap_get_range(get_range_fn, sheet):
        def _f(range_ref: str = None, range: str = None, **kw):
            ref = range_ref or range
            if ref is None:
                return {"error": "Missing range reference"}
            return get_range_fn(ref, sheet=sheet)
        return _f
    
    def _wrap_calculate(calculate_fn, sheet):
        def _f(formula: str = None, **kw):
            if not formula:
                return {"error": "Missing formula"}
            return calculate_fn(formula, sheet=sheet)
        return _f
    
    # Function to handle cross-sheet references in set_cell
    def set_cell_with_xref(cell_ref: str = None, cell: str = None, value: Any = None, **kwargs):
        # Accept either cell_ref or cell parameter name
        ref = cell_ref if cell_ref is not None else cell
        if ref is None:
            return {"error": "Missing cell reference parameter"}
        
        target_sheet = sheet
        
        # If the cell reference includes a sheet name (e.g., Sheet2!A1)
        if "!" in ref:
            sheet_name, cell_ref = ref.split("!", 1)
            try:
                target_sheet = workbook.sheet(sheet_name)
                return set_cell(cell_ref, value, sheet=target_sheet)
            except Exception as e:
                return {"error": f"Error with cross-sheet reference: {e}"}
        
        # Regular cell reference
        return set_cell(ref, value, sheet=target_sheet)
    
    # Function to handle set_cells with cross-sheet references
    def set_cells_with_xref(updates: list[dict[str, Any]] = None, cells_dict: dict[str, Any] = None, **kwargs):
        from collections import defaultdict
        results = []
        
        # Handle both parameter naming styles
        if updates is None and cells_dict is None:
            return {"error": "Missing updates parameter"}
        
        # Use whichever parameter is provided
        data = updates if updates is not None else cells_dict
        
        if isinstance(data, dict):
            # Convert dict format to list format for uniformity
            items = []
            for cell, value in data.items():
                items.append({"cell": cell, "value": value})
            data = items
        
        # Group by sheet
        sheet_cells = defaultdict(dict)
        
        for item in data:
            if isinstance(item, dict):
                cell = item.get("cell")
                value = item.get("value")
                
                if cell is None or value is None:
                    continue
                
                if "!" in cell:
                    sheet_name, cell_ref = cell.split("!", 1)
                    sheet_cells[sheet_name][cell_ref] = value
                else:
                    sheet_cells[sid][cell] = value
        
        # Apply changes by sheet
        for sheet_name, cells in sheet_cells.items():
            try:
                target_sheet = workbook.sheet(sheet_name)
                result = set_cells(cells, sheet=target_sheet)
                results.append(result)
            except Exception as e:
                results.append({"error": f"Error with sheet {sheet_name}: {e}"})
        
        return {"results": results}
    
    # Create partial functions for all tools with the sheet parameter
    tools = {
        "get_cell": _wrap_get_cell(get_cell, sheet),
        "get_range": _wrap_get_range(get_range, sheet),
        "summarize_sheet": partial(summarize_sheet, sheet=sheet),
        "calculate": _wrap_calculate(calculate, sheet),
        "set_cell": set_cell_with_xref,  # Use wrapper for cross-sheet references
        "add_row": partial(add_row, sheet=sheet),
        "add_column": partial(add_column, sheet=sheet),
        "delete_row": partial(delete_row, sheet=sheet),
        "delete_column": partial(delete_column, sheet=sheet),
        "sort_range": partial(sort_range, sheet=sheet),
        "find_replace": partial(find_replace, sheet=sheet),
        "create_new_sheet": partial(create_new_sheet, sheet=sheet),
        "get_row_by_header": partial(get_row_by_header, sheet=sheet),
        "get_column_by_header": partial(get_column_by_header, sheet=sheet),
        "apply_scalar_to_row": partial(apply_scalar_to_row, sheet=sheet),
        "apply_scalar_to_column": partial(apply_scalar_to_column, sheet=sheet),
        "set_cells": set_cells_with_xref,  # Use wrapper for cross-sheet references
        # New workbook-level tools
        "list_sheets": partial(list_sheets, wid=wid),
        "get_sheet_summary": lambda sid: get_sheet_summary(sid, wid=wid),
        "switch_sheet": lambda new_sid: {"status": "switched", "sheet": workbook.sheet(new_sid).to_dict()},
    }
    
    # Track updates made to the sheet
    collected_updates = []
    
    # Prepare system instructions with cross-sheet formula examples
    cross_sheet_instructions = """
You can now work with cross-sheet formulas. Examples:
1. To reference cells in other sheets, use Sheet2!A1 syntax
2. To create a formula that adds values from Sheet1 and Sheet2: =Sheet1!A1+Sheet2!B2
3. To update a cell with a cross-sheet reference: set_cell("Sheet2!A1", "=Sheet1!B3*2")
4. You can also navigate through different sheets to examine and modify data
5. When you need to set more than ~5 cells at once, **always use set_cells** with a dictionary so you don't hit the iteration cap.
"""
    
    # Update the tool functions in the agents
    if mode == "ask":
        # Clone the agent with updated tool functions
        agent = AskAgent.clone_with_tools(tools)
        # Add cross-sheet instructions
        agent.add_system_message(cross_sheet_instructions)
        result = await agent.run(message, history)
    elif mode == "analyst":
        # Clone the agent with updated tool functions
        agent = AnalystAgent.clone_with_tools(tools)
        # Add cross-sheet instructions
        agent.add_system_message(cross_sheet_instructions)
        result = await agent.run(message, history)
        
        # Collect the updates made during the agent's execution
        if "updates" in result:
            collected_updates = result["updates"]
    else:
        return {
            "reply": f"Invalid mode: {mode}. Please use 'ask' or 'analyst'.", 
            "sheet": sheet.to_dict(),
            "log": []
        }
    
    # Store the user message and assistant's reply in conversation history
    add_to_history(history_key, "user", message)
    add_to_history(history_key, "assistant", result["reply"])
    
    # Return the reply, updated sheet state, and log of changes
    return {
        "reply": result["reply"], 
        "sheet": sheet.optimized_to_dict(max_rows=30, max_cols=30),
        "all_sheets": {name: s.optimized_to_dict(max_rows=30, max_cols=30) for name, s in workbook.all_sheets().items()},
        "log": collected_updates
    } 