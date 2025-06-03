import asyncio
import time
import traceback
import os
import json  # Add missing json import
from typing import Dict, Any, Optional, AsyncGenerator
from functools import partial
from dotenv import load_dotenv

# Import the factory function instead of the provider registry
from llm.factory import get_client, get_default_client
from agents.ask_agent import build as build_ask_agent
from agents.analyst_agent import build as build_analyst_agent
from spreadsheet_engine.model import Spreadsheet
from spreadsheet_engine.summary import sheet_summary
from workbook_store import get_sheet, get_workbook
from chat.memory import get_history, add_to_history
from agents.base_agent import ChatStep
from chat.schemas import ChatRequest, ChatResponse
from spreadsheet_engine.operations import (
    get_cell, get_range, summarize_sheet, calculate,
    set_cell, add_row, add_column, delete_row, delete_column,
    sort_range, find_replace, create_new_sheet,
    get_row_by_header, get_column_by_header,
    apply_scalar_to_row, apply_scalar_to_column, set_cells,
    list_sheets, get_sheet_summary
)
from spreadsheet_engine.templates import dcf, fsm, loader as template_loader

# Flag to control template tools
ENABLE_TEMPLATES = os.getenv("ENABLE_TEMPLATE_TOOLS", "0") == "1"

async def process_message(
    mode: str, 
    message: str, 
    wid: str, 
    sid: str, 
    sheet=None, 
    workbook_metadata: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None  # Add model parameter
) -> Dict[str, Any]:
    """
    Process a message by routing it to the appropriate agent via the orchestrator.
    
    Args:
        mode: The agent mode ("ask" or "analyst")
        message: The user message to process
        wid: Workbook ID
        sid: Sheet ID in the workbook
        sheet: The spreadsheet to use (if None, uses get_sheet(wid, sid))
        workbook_metadata: Additional metadata about the workbook and its sheets
        model: Optional model string in format "provider:model_id"
        
    Returns:
        Dict with reply, sheet state, and log of updates
    """
    start_time = time.time()
    request_id = f"pm-{int(start_time*1000)}"
    print(f"[{request_id}] 🔄 process_message: mode={mode}, wid={wid}, sid={sid}, model={model}")
    
    try:
        # Use conversation history keyed by workbook ID only, not the sheet ID
        history_key = wid
        history = get_history(history_key)
        
        print(f"[{request_id}] 📚 Retrieved history for {history_key}: {len(history)} messages")
        
        # Get the sheet if not provided
        if sheet is None:
            print(f"[{request_id}] 🔍 Sheet not provided, getting from store")
            sheet = get_sheet(wid, sid)
            if not sheet:
                print(f"[{request_id}] ❌ Failed to get sheet {sid} from workbook {wid}")
                raise ValueError(f"Sheet {sid} not found in workbook {wid}")
        
        # Get the workbook
        workbook = get_workbook(wid)
        if not workbook:
            print(f"[{request_id}] ❌ Failed to get workbook {wid}")
            raise ValueError(f"Workbook {wid} not found")
        
        # Create workbook metadata if not provided
        if workbook_metadata is None:
            print(f"[{request_id}] 📊 Creating workbook metadata")
            all_sheets_data = {name: sheet_summary(s) for name, s in workbook.all_sheets().items()}
            workbook_metadata = {
                "sheets": workbook.list_sheets(),
                "active": sid,
                "all_sheets_data": all_sheets_data
            }
        
        # Inject current workbook/sheet info into history for LLM context
        sheet_info = sheet_summary(sheet)
        system_context = (
            f"Workbook: {wid}\nCurrent sheet: {sid}\n"
            f"Available sheets: {', '.join(workbook_metadata['sheets'])}\n\n"
            f"You can reference cells across sheets using Sheet2!A1 syntax in formulas.\n"
            f"For example, =Sheet2!A1+Sheet3!B2 adds values from two different sheets.\n\n"
            f"Current sheet summary: {json.dumps(sheet_info)}\n"
            f"Call get_range or sheet_summary tools if you need more detail on the sheet."
        )
        
        # Add instruction on creating new sheets
        system_context += (
            "\n\nYou can create additional sheets with the create_new_sheet tool. "
            "If you need a balance sheet, call create_new_sheet(name='Sheet2') first."
        )
        
        # Add tools quick-reference
        system_context += (
            "\n\nTOOLS QUICK-REFERENCE:\n"
            "• set_cell(cell=\"A1\", value=42) – update ONE cell.\n"
            "• set_cells(updates=[{\"cell\":\"A1\", \"value\":42},{\"cell\":\"B1\", \"value\":99}]) "
            "OR set_cells(cells_dict={\"A1\":42, \"B1\":99}) – update MULTIPLE cells.\n"
            "Either tool is acceptable – the backend now auto-batches many set_cell calls."
        )
        
        # Add any context ranges if provided
        contexts = workbook_metadata.get('contexts', [])
        if contexts:
            context_data = []
            for i, context_range in enumerate(contexts, 1):
                try:
                    # Split sheet name from range if present (e.g., Sheet2!A1:B3)
                    if '!' in context_range:
                        sheet_name, range_ref = context_range.split('!', 1)
                        context_sheet = workbook.sheet(sheet_name)
                    else:
                        context_sheet = sheet
                        range_ref = context_range
                    
                    # Get the range values
                    if context_sheet:
                        range_data = context_sheet.get_range(range_ref)
                        # Format the range data as a simple table
                        rows_str = []
                        for row in range_data:
                            row_str = ",".join(str(cell) for cell in row)
                            rows_str.append(row_str)
                        
                        # Add to context data
                        context_str = f"### Context {i} ({context_range})\n" + "\n".join(rows_str)
                        context_data.append(context_str)
                except Exception as e:
                    print(f"Error getting context range {context_range}: {e}")
                    context_data.append(f"### Context {i} ({context_range})\nError: Unable to retrieve data")
            
            # Add contexts to system prompt if any were processed successfully
            if context_data:
                system_context += "\n\n" + "\n\n".join(context_data)
                system_context += "\n\nRefer to the numbered contexts above in your response as needed."
        
        print(f"[{request_id}] 📝 Injecting system context with {len(workbook_metadata['sheets'])} sheets")
        
        history.insert(0, {
            "role": "system", 
            "content": system_context
        })
        
        # Create partial functions for all tools with the sheet parameter
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
        def set_cell_with_xref(cell_ref: str = None, cell: str = None, value: Any = None, allow_formula: bool = False, **kwargs):
            # Accept either cell_ref or cell parameter name
            ref = cell_ref if cell_ref is not None else cell
            
            # Enhanced debugging and validation
            print(f"[{request_id}] 🔧 set_cell_with_xref called: cell_ref='{cell_ref}', cell='{cell}', value='{value}', kwargs={kwargs}")
            
            # Check for completely missing parameters
            if ref is None:
                print(f"[{request_id}] ⚠️ Both cell_ref and cell parameters are None")
                return {
                    "error": "MISSING_CELL_REFERENCE", 
                    "message": "You must provide a valid cell reference like 'A1', 'B2', etc. Both 'cell_ref' and 'cell' parameters are missing.",
                    "example": "Call set_cell with: set_cell(cell='A1', value='Hello')",
                    "debug": {
                        "cell_ref": cell_ref,
                        "cell": cell,
                        "value": value,
                        "kwargs": kwargs
                    }
                }
            
            # Check for empty string after converting to string and stripping
            ref_str = str(ref).strip() if ref is not None else ""
            if not ref_str:
                print(f"[{request_id}] ⚠️ Empty cell reference after stripping: '{ref}' -> '{ref_str}'")
                return {
                    "error": "EMPTY_CELL_REFERENCE", 
                    "message": "You must provide a valid cell reference like 'A1', 'B2', etc. The cell reference cannot be empty.",
                    "example": "Call set_cell with: set_cell(cell='A1', value='Hello')",
                    "debug": {
                        "original_ref": ref,
                        "stripped_ref": ref_str,
                        "cell_ref": cell_ref,
                        "cell": cell,
                        "value": value
                    }
                }
            
            # Use the cleaned reference
            ref = ref_str
            target_sheet = sheet
            
            # If the cell reference includes a sheet name (e.g., Sheet2!A1)
            if "!" in ref:
                sheet_name, cell_ref = ref.split("!", 1)
                try:
                    target_sheet = workbook.sheet(sheet_name)
                    print(f"[{request_id}] 📝 Cross-sheet set_cell: {sheet_name}!{cell_ref} = {value}")
                    return set_cell(cell_ref, value, sheet=target_sheet)
                except Exception as e:
                    print(f"[{request_id}] ❌ Error with cross-sheet reference: {e}")
                    return {"error": f"Error with cross-sheet reference: {e}"}
            
            # Regular cell reference
            print(f"[{request_id}] 📝 Setting cell {ref} = {value} in sheet {sid}")
            
            # Check if value is a formula and formulas are allowed
            is_formula = isinstance(value, str) and value.strip().startswith('=')
            if is_formula and not allow_formula:
                print(f"[{request_id}] 🔄 Formula detected in {ref}: {value}")
            
            # Include formula flag if value is a formula
            result = set_cell(ref, value, sheet=target_sheet)
            if is_formula:
                result['allow_formula'] = allow_formula
            
            return result
        
        # Function to handle set_cells with cross-sheet references
        def set_cells_with_xref(updates: list[dict[str, Any]] = None, cells_dict: dict[str, Any] = None, allow_formulas: bool = False, **kwargs):
            from collections import defaultdict
            results = []
            
            # Handle both parameter naming styles
            if updates is None and cells_dict is None:
                return {"error": "No updates provided. Pass either 'updates' or 'cells_dict'"}
            
            # Convert cells_dict to updates list if provided
            if cells_dict is not None and isinstance(cells_dict, dict):
                updates = [{"cell": cell, "value": value} for cell, value in cells_dict.items()]
            
            if not updates:
                return {"error": "No updates provided"}
            
            # Group updates by sheet
            sheet_updates = defaultdict(list)
            
            # Check if any update contains a formula
            has_formulas = False
            for update in updates:
                if isinstance(update, dict) and "cell" in update:
                    value = update.get("value", update.get("new_value", update.get("new", None)))
                    if isinstance(value, str) and value.strip().startswith('='):
                        has_formulas = True
                        # Add formula flag to the update
                        update['allow_formula'] = allow_formulas
            
            for update in updates:
                # Skip invalid update objects
                if not isinstance(update, dict) or "cell" not in update:
                    print(f"[{request_id}] ⚠️ Skipping invalid update object: {update}")
                    continue
                    
                cell_ref = update["cell"]
                
                # Validate cell reference
                if not cell_ref or not str(cell_ref).strip():
                    print(f"[{request_id}] ⚠️ Skipping update with empty cell reference: '{cell_ref}'")
                    continue
                
                value = update.get("value", update.get("new_value", update.get("new", None)))
                
                # If the cell reference includes a sheet name (e.g., Sheet2!A1)
                if "!" in cell_ref:
                    sheet_name, ref = cell_ref.split("!", 1)
                    sheet_updates[sheet_name].append(update)
                else:
                    sheet_updates[sid].append(update)
            
            # Apply updates to each sheet
            for target_sid, sheet_updates_list in sheet_updates.items():
                try:
                    target_sheet = workbook.sheet(target_sid)
                    if not target_sheet:
                        results.append({"error": f"Sheet {target_sid} not found"})
                        continue
                        
                    for update in sheet_updates_list:
                        cell_ref = update["cell"]
                        if "!" in cell_ref:
                            _, cell_ref = cell_ref.split("!", 1)
                        
                        value = update.get("value", update.get("new_value", update.get("new", None)))
                        allow_formula = update.get("allow_formula", False)
                        
                        # Pass allow_formula flag if it exists
                        if isinstance(value, str) and value.strip().startswith('='):
                            result = set_cell(cell_ref, value, sheet=target_sheet)
                            result['allow_formula'] = allow_formula
                        else:
                            result = set_cell(cell_ref, value, sheet=target_sheet)
                        
                        # Add sheet information to the result
                        result["sheet_id"] = target_sid
                        results.append(result)
                except Exception as e:
                    results.append({"error": f"Error updating sheet {target_sid}: {str(e)}"})
            
            # Return a new empty update if results is still empty (avoid errors)
            if not results:
                results.append({"cell": "A1", "new_value": "", "kind": "no_change"})
                
            return {"updates": results, "has_formulas": has_formulas}
        
        # Function to apply batch updates and generate a final reply in one step
        def apply_updates_and_reply(updates: list[dict[str, Any]] = None, reply: str = None, allow_formulas: bool = False, **kwargs):
            if updates is None:
                updates = []
                
            # CRITICAL: Reject empty updates
            if not updates:
                return {"error": "apply_updates_and_reply requires at least one update. Use individual tools like set_cell for single updates."}
                
            if not reply:
                reply = f"Applied {len(updates)} updates."
            
            # LIMIT RESPONSE LENGTH - truncate if too long
            max_reply_length = 800  # Reasonable limit for streaming
            if len(reply) > max_reply_length:
                reply = reply[:max_reply_length] + "..."
                print(f"[{request_id}] ✂️ Truncated reply from {len(reply)} to {max_reply_length} chars")
            
            # Check if the reply mentions formulas being added
            formula_keywords = ["formula", "formulas", "calculation", "calculations", "= sign", "equals sign"]
            formula_requested = allow_formulas or any(keyword.lower() in reply.lower() for keyword in formula_keywords)
            
            # Apply the updates with formula flag if formulas were requested
            result = set_cells_with_xref(updates=updates, allow_formulas=formula_requested)
            
            # Add our reply
            result["reply"] = reply
            
            return result
        
        # Prepare all the tool functions
        tool_functions = {
            "get_cell": _wrap_get_cell(get_cell, sheet),
            "get_range": _wrap_get_range(get_range, sheet),
            "calculate": _wrap_calculate(calculate, sheet),
            "sheet_summary": partial(summarize_sheet, sheet=sheet),
            "set_cell": set_cell_with_xref,
            "set_cells": set_cells_with_xref,
            "apply_updates_and_reply": apply_updates_and_reply,
            "add_row": partial(add_row, sheet=sheet),
            "add_column": partial(add_column, sheet=sheet),
            "delete_row": partial(delete_row, sheet=sheet),
            "delete_column": partial(delete_column, sheet=sheet),
            "sort_range": partial(sort_range, sheet=sheet),
            "find_replace": partial(find_replace, sheet=sheet),
            "get_row_by_header": partial(get_row_by_header, sheet=sheet),
            "get_column_by_header": partial(get_column_by_header, sheet=sheet),
            "apply_scalar_to_row": partial(apply_scalar_to_row, sheet=sheet),
            "apply_scalar_to_column": partial(apply_scalar_to_column, sheet=sheet),
            "create_new_sheet": partial(create_new_sheet, sheet=sheet),
            "list_sheets": partial(list_sheets, wid=wid),
            "get_sheet_summary": partial(get_sheet_summary, wid=wid),
        }
        
        # Add template tools only if enabled
        if ENABLE_TEMPLATES:
            template_functions = {
                "insert_template_sheets": partial(template_loader.insert_template_sheets, wb=workbook),
                "insert_fsm_template": partial(fsm.insert_template, workbook=workbook),
                "insert_dcf_template": partial(dcf.insert_template, workbook=workbook),
                "insert_dcf_model": partial(dcf.build_dcf, wb=workbook),
                "insert_fsm_model": partial(fsm.build_fsm, wb=workbook)
            }
            # Add the template tools to the tool functions
            tool_functions.update(template_functions)
            
        # For ask mode, restrict to read-only tools
        if mode == "ask":
            read_only_tools = {k: v for k, v in tool_functions.items() 
                              if k in {"get_cell", "get_range", "sheet_summary", "calculate"}}
            tool_functions = read_only_tools
        
        # Set up LLM client using factory
        try:
            if model:
                print(f"[{request_id}] 🔄 Using explicit model: {model}")
                llm_client = get_client(model)
            else:
                # Use default model from environment
                llm_client = get_default_client()
                print(f"[{request_id}] 🔄 Using default model: {llm_client.model}")
        except Exception as e:
            print(f"[{request_id}] ❌ Error initializing LLM client: {e}")
            raise ValueError(f"Error initializing LLM client: {e}")
        
        # Initialize the orchestrator with the LLM client and tools
        from agents.orchestrator import Orchestrator
        orchestrator = Orchestrator(
            llm=llm_client,
            sheet=sheet,
            tool_functions=tool_functions
        )
        
        # Create sheet context summary
        summary = sheet_summary(sheet)
        ctx = f"[Context] Active sheet '{summary['name']}' has {summary['n_rows']} rows × {summary['n_cols']} cols; Headers: {summary['headers']}."
        
        # Run the orchestrator with the given mode
        print(f"[{request_id}] 🧠 Running orchestrator with mode={mode}")
        start_run = time.time()
        result = await orchestrator.run(mode, message, history)
        run_time = time.time() - start_run
        
        # Process the result - will differ based on agent type but should have "reply" at minimum
        if not result or "reply" not in result:
            print(f"[{request_id}] ⚠️ Empty or invalid result from orchestrator")
            result = {"reply": "I'm sorry, I couldn't process your request properly.", "updates": []}
        
        # Add current sheet state to result
        sheet_output = sheet.to_dict()
        result["sheet"] = sheet_output
        
        # Add a debug log that can be used by the frontend 
        result["log"] = []  # empty for now, could include token counts or other metadata
        
        # Save conversation history - message pairs only
        add_to_history(history_key, "user", message)
        add_to_history(history_key, "assistant", result["reply"])
        
        # Done!
        print(f"[{request_id}] ✅ Completed in {run_time:.2f}s with {len(result.get('updates', []))} updates")
        print(f"[{request_id}] 💬 Response: {result['reply'][:100]}...")
        
        return result
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        traceback.print_exc()
        raise e

async def process_message_streaming(
    mode: str, 
    message: str, 
    wid: str, 
    sid: str, 
    sheet=None, 
    workbook_metadata: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None  # Add model parameter
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Process a message with streaming response using the orchestrator.
    
    Args:
        mode: The agent mode ("ask" or "analyst")
        message: The user message to process
        wid: Workbook ID
        sid: Sheet ID in the workbook
        sheet: The spreadsheet to use (if None, uses get_sheet(wid, sid))
        workbook_metadata: Additional metadata about the workbook and its sheets
        model: Optional model string in format "provider:model_id"
        
    Yields:
        Dict with partial response text chunks
    """
    start_time = time.time()
    request_id = f"pm-stream-{int(start_time*1000)}"
    print(f"[{request_id}] 🔄 process_message_streaming: mode={mode}, wid={wid}, sid={sid}, model={model}")
    print(f"[{request_id}] 📝 Message: {message[:100]}{'...' if len(message) > 100 else ''}")
    
    try:
        # Get history, sheet, and workbook - same as process_message
        history_key = wid
        history = get_history(history_key)
        
        if sheet is None:
            sheet = get_sheet(wid, sid)
            if not sheet:
                print(f"[{request_id}] ❌ Failed to get sheet {sid} from workbook {wid}")
                raise ValueError(f"Sheet {sid} not found in workbook {wid}")
        
        workbook = get_workbook(wid)
        if not workbook:
            print(f"[{request_id}] ❌ Failed to get workbook {wid}")
            raise ValueError(f"Workbook {wid} not found")
        
        # Create workbook metadata if not provided
        if workbook_metadata is None:
            all_sheets_data = {name: sheet_summary(s) for name, s in workbook.all_sheets().items()}
            workbook_metadata = {
                "sheets": workbook.list_sheets(),
                "active": sid,
                "all_sheets_data": all_sheets_data
            }
        
        # Inject system context - same as process_message
        sheet_info = sheet_summary(sheet)
        system_context = (
            f"Workbook: {wid}\nCurrent sheet: {sid}\n"
            f"Available sheets: {', '.join(workbook_metadata['sheets'])}\n\n"
            f"You can reference cells across sheets using Sheet2!A1 syntax in formulas.\n"
            f"For example, =Sheet2!A1+Sheet3!B2 adds values from two different sheets.\n\n"
            f"Current sheet summary: {json.dumps(sheet_info)}\n"
            f"Call get_range or sheet_summary tools if you need more detail on the sheet."
        )
        
        # Add instruction on creating new sheets
        system_context += (
            "\n\nYou can create additional sheets with the create_new_sheet tool. "
            "If you need a balance sheet, call create_new_sheet(name='Sheet2') first."
        )
        
        # Add tools quick-reference
        system_context += (
            "\n\nTOOLS QUICK-REFERENCE:\n"
            "• set_cell(cell=\"A1\", value=42) – update ONE cell.\n"
            "• set_cells(updates=[{\"cell\":\"A1\", \"value\":42},{\"cell\":\"B1\", \"value\":99}]) "
            "OR set_cells(cells_dict={\"A1\":42, \"B1\":99}) – update MULTIPLE cells.\n"
            "Either tool is acceptable – the backend now auto-batches many set_cell calls."
        )
        
        # Add any context ranges if provided
        contexts = workbook_metadata.get('contexts', [])
        if contexts:
            context_data = []
            for i, context_range in enumerate(contexts, 1):
                try:
                    # Split sheet name from range if present (e.g., Sheet2!A1:B3)
                    if '!' in context_range:
                        sheet_name, range_ref = context_range.split('!', 1)
                        context_sheet = workbook.sheet(sheet_name)
                    else:
                        context_sheet = sheet
                        range_ref = context_range
                    
                    # Get the range values
                    if context_sheet:
                        range_data = context_sheet.get_range(range_ref)
                        # Format the range data as a simple table
                        rows_str = []
                        for row in range_data:
                            row_str = ",".join(str(cell) for cell in row)
                            rows_str.append(row_str)
                        
                        # Add to context data
                        context_str = f"### Context {i} ({context_range})\n" + "\n".join(rows_str)
                        context_data.append(context_str)
                except Exception as e:
                    print(f"Error getting context range {context_range}: {e}")
                    context_data.append(f"### Context {i} ({context_range})\nError: Unable to retrieve data")
            
            # Add contexts to system prompt if any were processed successfully
            if context_data:
                system_context += "\n\n" + "\n\n".join(context_data)
                system_context += "\n\nRefer to the numbered contexts above in your response as needed."
        
        history.insert(0, {
            "role": "system", 
            "content": system_context
        })
        
        # Create wrapper functions for tools - same as process_message
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
        
        # Function to handle cross-sheet references - same as process_message
        def set_cell_with_xref(cell_ref: str = None, cell: str = None, value: Any = None, allow_formula: bool = False, **kwargs):
            # Accept either cell_ref or cell parameter name
            ref = cell_ref if cell_ref is not None else cell
            
            # Enhanced debugging and validation
            print(f"[{request_id}] 🔧 set_cell_with_xref called: cell_ref='{cell_ref}', cell='{cell}', value='{value}', kwargs={kwargs}")
            
            # Check for completely missing parameters
            if ref is None:
                print(f"[{request_id}] ⚠️ Both cell_ref and cell parameters are None")
                return {
                    "error": "MISSING_CELL_REFERENCE", 
                    "message": "You must provide a valid cell reference like 'A1', 'B2', etc. Both 'cell_ref' and 'cell' parameters are missing.",
                    "example": "Call set_cell with: set_cell(cell='A1', value='Hello')",
                    "debug": {
                        "cell_ref": cell_ref,
                        "cell": cell,
                        "value": value,
                        "kwargs": kwargs
                    }
                }
            
            # Check for empty string after converting to string and stripping
            ref_str = str(ref).strip() if ref is not None else ""
            if not ref_str:
                print(f"[{request_id}] ⚠️ Empty cell reference after stripping: '{ref}' -> '{ref_str}'")
                return {
                    "error": "EMPTY_CELL_REFERENCE", 
                    "message": "You must provide a valid cell reference like 'A1', 'B2', etc. The cell reference cannot be empty.",
                    "example": "Call set_cell with: set_cell(cell='A1', value='Hello')",
                    "debug": {
                        "original_ref": ref,
                        "stripped_ref": ref_str,
                        "cell_ref": cell_ref,
                        "cell": cell,
                        "value": value
                    }
                }
            
            # Use the cleaned reference
            ref = ref_str
            target_sheet = sheet
            
            # If the cell reference includes a sheet name (e.g., Sheet2!A1)
            if "!" in ref:
                sheet_name, cell_ref = ref.split("!", 1)
                try:
                    target_sheet = workbook.sheet(sheet_name)
                    print(f"[{request_id}] 📝 Cross-sheet set_cell: {sheet_name}!{cell_ref} = {value}")
                    return set_cell(cell_ref, value, sheet=target_sheet)
                except Exception as e:
                    print(f"[{request_id}] ❌ Error with cross-sheet reference: {e}")
                    return {"error": f"Error with cross-sheet reference: {e}"}
            
            # Regular cell reference
            print(f"[{request_id}] 📝 Setting cell {ref} = {value} in sheet {sid}")
            
            # Check if value is a formula and formulas are allowed
            is_formula = isinstance(value, str) and value.strip().startswith('=')
            if is_formula and not allow_formula:
                print(f"[{request_id}] 🔄 Formula detected in {ref}: {value}")
            
            # Include formula flag if value is a formula
            result = set_cell(ref, value, sheet=target_sheet)
            if is_formula:
                result['allow_formula'] = allow_formula
            
            return result
        
        # Function to handle set_cells with cross-sheet references - same as process_message
        def set_cells_with_xref(updates: list[dict[str, Any]] = None, cells_dict: dict[str, Any] = None, allow_formulas: bool = False, **kwargs):
            from collections import defaultdict
            results = []
            
            # Handle both parameter naming styles
            if updates is None and cells_dict is None:
                return {"error": "No updates provided. Pass either 'updates' or 'cells_dict'"}
            
            # Convert cells_dict to updates list if provided
            if cells_dict is not None and isinstance(cells_dict, dict):
                updates = [{"cell": cell, "value": value} for cell, value in cells_dict.items()]
            
            if not updates:
                return {"error": "No updates provided"}
            
            # Group updates by sheet
            sheet_updates = defaultdict(list)
            
            # Check if any update contains a formula
            has_formulas = False
            for update in updates:
                if isinstance(update, dict) and "cell" in update:
                    value = update.get("value", update.get("new_value", update.get("new", None)))
                    if isinstance(value, str) and value.strip().startswith('='):
                        has_formulas = True
                        # Add formula flag to the update
                        update['allow_formula'] = allow_formulas
            
            for update in updates:
                # Skip invalid update objects
                if not isinstance(update, dict) or "cell" not in update:
                    print(f"[{request_id}] ⚠️ Skipping invalid update object: {update}")
                    continue
                    
                cell_ref = update["cell"]
                
                # Validate cell reference
                if not cell_ref or not str(cell_ref).strip():
                    print(f"[{request_id}] ⚠️ Skipping update with empty cell reference: '{cell_ref}'")
                    continue
                
                value = update.get("value", update.get("new_value", update.get("new", None)))
                
                # If the cell reference includes a sheet name (e.g., Sheet2!A1)
                if "!" in cell_ref:
                    sheet_name, ref = cell_ref.split("!", 1)
                    sheet_updates[sheet_name].append(update)
                else:
                    sheet_updates[sid].append(update)
            
            # Apply updates to each sheet
            for target_sid, sheet_updates_list in sheet_updates.items():
                try:
                    target_sheet = workbook.sheet(target_sid)
                    if not target_sheet:
                        results.append({"error": f"Sheet {target_sid} not found"})
                        continue
                        
                    for update in sheet_updates_list:
                        cell_ref = update["cell"]
                        if "!" in cell_ref:
                            _, cell_ref = cell_ref.split("!", 1)
                        
                        value = update.get("value", update.get("new_value", update.get("new", None)))
                        allow_formula = update.get("allow_formula", False)
                        
                        # Pass allow_formula flag if it exists
                        if isinstance(value, str) and value.strip().startswith('='):
                            result = set_cell(cell_ref, value, sheet=target_sheet)
                            result['allow_formula'] = allow_formula
                        else:
                            result = set_cell(cell_ref, value, sheet=target_sheet)
                        
                        # Add sheet information to the result
                        result["sheet_id"] = target_sid
                        results.append(result)
                except Exception as e:
                    results.append({"error": f"Error updating sheet {target_sid}: {str(e)}"})
            
            # Return a new empty update if results is still empty (avoid errors)
            if not results:
                results.append({"cell": "A1", "new_value": "", "kind": "no_change"})
                
            return {"updates": results, "has_formulas": has_formulas}
        
        # Function to apply batch updates and generate a final reply in one step
        def apply_updates_and_reply(updates: list[dict[str, Any]] = None, reply: str = None, allow_formulas: bool = False, **kwargs):
            print(f"[{request_id}] 🔧 apply_updates_and_reply called with {len(updates) if updates else 0} updates")
            print(f"[{request_id}] 💬 Reply: {reply[:100] if reply else 'None'}{'...' if reply and len(reply) > 100 else ''}")
            print(f"[{request_id}] 📊 All args: updates={len(updates) if updates else 0}, allow_formulas={allow_formulas}, kwargs={kwargs}")
            
            if updates is None:
                updates = []
                
            # CRITICAL: Reject empty updates
            if not updates:
                error_msg = "apply_updates_and_reply requires at least one update. Use individual tools like set_cell for single updates."
                print(f"[{request_id}] ❌ Empty updates error: {error_msg}")
                return {"error": error_msg}
                
            if not reply:
                reply = f"Applied {len(updates)} updates."
            
            # LIMIT RESPONSE LENGTH - truncate if too long
            max_reply_length = 800  # Reasonable limit for streaming
            if len(reply) > max_reply_length:
                reply = reply[:max_reply_length] + "..."
                print(f"[{request_id}] ✂️ Truncated reply from {len(reply)} to {max_reply_length} chars")
            
            # Check if the reply mentions formulas being added
            formula_keywords = ["formula", "formulas", "calculation", "calculations", "= sign", "equals sign"]
            formula_requested = allow_formulas or any(keyword.lower() in reply.lower() for keyword in formula_keywords)
            
            # Apply the updates with formula flag if formulas were requested
            print(f"[{request_id}] 📊 Applying {len(updates)} updates with formulas={formula_requested}")
            for i, update in enumerate(updates[:3]):  # Log first 3 updates
                print(f"[{request_id}] 📝 Update {i+1}: {update}")
            
            result = set_cells_with_xref(updates=updates, allow_formulas=formula_requested)
            
            # Add our reply
            result["reply"] = reply
            print(f"[{request_id}] ✅ apply_updates_and_reply completed with {len(result.get('updates', []))} applied updates")
            
            return result
        
        # Create a streaming wrapper for tool functions
        def create_streaming_wrapper(tool_fn, name):
            """Create a wrapper that logs the call"""
            def wrapper(*args, **kwargs):
                print(f"[{request_id}] 🔧 Streaming tool call: {name}")
                
                # ENHANCED DEBUGGING for tool wrapper calls
                print(f"[{request_id}] 🔍 TOOL WRAPPER DEBUG:")
                print(f"[{request_id}] 📝 Tool name: '{name}'")
                print(f"[{request_id}] 📝 Args type: {type(args)}")
                print(f"[{request_id}] 📝 Args content: {repr(args)}")
                print(f"[{request_id}] 📝 Args length: {len(args) if args else 0}")
                print(f"[{request_id}] 📝 Kwargs type: {type(kwargs)}")
                print(f"[{request_id}] 📝 Kwargs content: {repr(kwargs)}")
                print(f"[{request_id}] 📝 Kwargs length: {len(kwargs) if kwargs else 0}")
                
                # Add detailed logging for debugging
                print(f"[{request_id}] 📊 Tool args: {json.dumps(args, default=str)[:200] if args else 'None'}...")
                print(f"[{request_id}] 📊 Tool kwargs: {json.dumps(kwargs, default=str)[:200] if kwargs else 'None'}...")
                
                # Tools that need special handling
                financial_model_tools = ["insert_fsm_model", "insert_dcf_model", "insert_fsm_template", "insert_dcf_template"]
                sheet_tools = ["create_new_sheet"]
                table_tools = ["add_column", "add_row", "delete_column", "delete_row", "sort_range", "find_replace"]
                cell_tools = ["set_cell", "get_cell", "get_range"]
                
                # Ensure that kwargs is always a dictionary
                if len(args) == 1 and isinstance(args[0], str) and not kwargs:
                    # Handle the case where a single string argument is passed
                    # This happens with some tools when called with just a string
                    print(f"[{request_id}] 🔄 Handling single string argument: '{args[0]}'")
                    
                    if name == "set_cell":
                        # For set_cell, we need cell and value parameters
                        # Check if the string is in "A1=value" format
                        if "=" in args[0]:
                            cell_ref, value = args[0].split("=", 1)
                            return tool_fn(cell=cell_ref.strip(), value=value.strip())
                        else:
                            # If there's no equals sign, it might just be a cell reference
                            # We'll set an empty string as the value
                            return tool_fn(cell=args[0], value="")
                    elif name == "get_cell":
                        return tool_fn(cell_ref=args[0])
                    elif name == "get_range":
                        return tool_fn(range_ref=args[0])
                    elif name == "create_new_sheet":
                        # Handle create_new_sheet with a string argument as the name parameter
                        return tool_fn(name=args[0])
                    elif name == "add_column" or name == "add_row":
                        # For add_column and add_row, use the header parameter for the string
                        return tool_fn(header=args[0])
                    elif name == "set_cells":
                        # Special handling for set_cells with string argument
                        # Try to parse as JSON if it looks like a JSON string
                        if args[0].strip().startswith('{') or args[0].strip().startswith('['):
                            try:
                                data = json.loads(args[0])
                                if isinstance(data, dict):
                                    # Handle dict format (cells_dict)
                                    return tool_fn(cells_dict=data)
                                elif isinstance(data, list):
                                    # Handle list format (updates)
                                    return tool_fn(updates=data)
                                else:
                                    return {"error": f"Invalid JSON format for set_cells: {args[0]}"}
                            except json.JSONDecodeError:
                                return {"error": f"Could not parse JSON for set_cells: {args[0]}"}
                        # If it's not JSON, try to interpret as a simple "A1=value" format
                        elif "=" in args[0]:
                            cell_ref, value = args[0].split("=", 1)
                            update = [{"cell": cell_ref.strip(), "value": value.strip()}]
                            return tool_fn(updates=update)
                        else:
                            return {"error": f"Invalid format for set_cells. Expected JSON or A1=value format, got: {args[0]}"}
                    elif name in financial_model_tools:
                        # Prevent financial model tools from being called with incorrect arguments
                        # or when not specifically requested
                        print(f"[{request_id}] ⚠️ Preventing inappropriate call to {name} with string argument")
                        return {"error": f"The {name} tool requires specific parameters, not a string."}
                    elif name in table_tools:
                        # Handle other table manipulation tools safely
                        print(f"[{request_id}] ⚠️ The {name} tool requires specific parameters, not a string.")
                        return {"error": f"The {name} tool requires specific parameters. Please provide complete arguments."}
                    else:
                        # For other functions, pass as first argument if possible, otherwise try as a keyword arg
                        try:
                            # First, try to infer the parameter name based on function signature
                            import inspect
                            sig = inspect.signature(tool_fn)
                            params = list(sig.parameters.keys())
                            
                            # If we have parameters, use the first one as the keyword
                            if params:
                                # Create a kwargs dict with the first parameter name
                                param_kwargs = {params[0]: args[0]}
                                return tool_fn(**param_kwargs)
                            else:
                                # Just try passing it through
                                return tool_fn(args[0])
                        except TypeError as e:
                            print(f"[{request_id}] ⚠️ Error calling {name}: {str(e)}")
                            return {"error": f"Invalid parameters for {name}: {str(e)}"}
                elif len(args) == 0 and len(kwargs) == 0:
                    # Handle completely empty tool calls
                    print(f"[{request_id}] ⚠️ Empty tool call detected for {name}")
                    if name == "set_cell":
                        return {"error": "set_cell requires cell and value parameters. Example: set_cell(cell='A1', value='Hello')"}
                    elif name == "set_cells":
                        return {"error": "set_cells requires updates parameter. Example: set_cells(updates=[{'cell': 'A1', 'value': 'Hello'}])"}
                    elif name == "apply_updates_and_reply":
                        return {"error": "apply_updates_and_reply requires updates parameter. Example: apply_updates_and_reply(updates=[{'cell': 'A1', 'value': 'Hello'}], reply='Updated cell A1')"}
                    else:
                        return {"error": f"The {name} tool requires parameters. Please provide the necessary arguments."}
                elif name == "set_cell" and len(args) == 2:
                    # Handle case where set_cell is called with (cell, value) positional args
                    cell_ref = args[0]
                    if not cell_ref or not cell_ref.strip():
                        return {"error": "Invalid empty cell reference for set_cell"}
                    return tool_fn(cell=cell_ref, value=args[1])
                else:
                    # Normal case - keyword arguments
                    try:
                        print(f"[{request_id}] 🧰 Executing {name}")
                        
                        # Add detailed logging for debugging tool calls
                        print(f"[{request_id}] 🔧 Tool: {name}, Args: {json.dumps(args, default=str)[:200]}...")
                        
                        fn_start = time.time()
                        result = tool_fn(*args, **kwargs)
                        fn_end = time.time()
                        fn_duration = fn_end - fn_start
                        print(f"[{request_id}] 🚀 {name} completed in {fn_duration:.2f}s")
                        return result
                    except TypeError as e:
                        print(f"[{request_id}] ⚠️ Error calling {name} with {args} and {kwargs}: {str(e)}")
                        return {"error": f"Invalid parameters for {name}: {str(e)}"}
            return wrapper
            
        # Prepare all the tool functions with streaming wrappers
        tool_functions = {}
        for name, fn in {
            "get_cell": _wrap_get_cell(get_cell, sheet),
            "get_range": _wrap_get_range(get_range, sheet),
            "calculate": _wrap_calculate(calculate, sheet),
            "sheet_summary": partial(summarize_sheet, sheet=sheet),
            "set_cell": set_cell_with_xref,
            "set_cells": set_cells_with_xref,
            "apply_updates_and_reply": apply_updates_and_reply,
            "add_row": partial(add_row, sheet=sheet),
            "add_column": partial(add_column, sheet=sheet),
            "delete_row": partial(delete_row, sheet=sheet),
            "delete_column": partial(delete_column, sheet=sheet),
            "sort_range": partial(sort_range, sheet=sheet),
            "find_replace": partial(find_replace, sheet=sheet),
            "get_row_by_header": partial(get_row_by_header, sheet=sheet),
            "get_column_by_header": partial(get_column_by_header, sheet=sheet),
            "apply_scalar_to_row": partial(apply_scalar_to_row, sheet=sheet),
            "apply_scalar_to_column": partial(apply_scalar_to_column, sheet=sheet),
            "create_new_sheet": partial(create_new_sheet, sheet=sheet),
            "list_sheets": partial(list_sheets, wid=wid),
            "get_sheet_summary": partial(get_sheet_summary, wid=wid),
        }.items():
            tool_functions[name] = create_streaming_wrapper(fn, name)
        
        # Template-specific tools
        for name, fn in {
            "insert_fsm_template": partial(fsm.insert_template, workbook=workbook),
            "insert_dcf_template": partial(dcf.insert_template, workbook=workbook),
            "insert_dcf_model": partial(dcf.build_dcf, wb=workbook),
            "insert_fsm_model": partial(fsm.build_fsm, wb=workbook)
        }.items():
            tool_functions[name] = create_streaming_wrapper(fn, name)
        
        # For ask mode, restrict to read-only tools
        if mode == "ask":
            # Only provide read-only tools in ask mode
            read_only_tools = {
                "get_cell": _wrap_get_cell(get_cell, sheet),
                "get_range": _wrap_get_range(get_range, sheet),
                "sheet_summary": partial(summarize_sheet, sheet=sheet),
                "calculate": _wrap_calculate(calculate, sheet)
            }
            tool_functions = {name: create_streaming_wrapper(fn, name) for name, fn in read_only_tools.items()}
        
        # Set up LLM client using factory
        try:
            if model:
                print(f"[{request_id}] 🔄 Using explicit model: {model}")
                llm_client = get_client(model)
                print(f"[{request_id}] ✅ LLM client created: {llm_client.__class__.__name__}")
            else:
                # Use default model from environment
                llm_client = get_default_client()
                print(f"[{request_id}] 🔄 Using default model: {llm_client.model}")
                print(f"[{request_id}] ✅ Default LLM client created: {llm_client.__class__.__name__}")
        except Exception as e:
            print(f"[{request_id}] ❌ Error initializing LLM client: {e}")
            traceback.print_exc()
            yield {"error": f"Error initializing LLM client: {e}"}
            return
        
        # Initialize the orchestrator with the LLM client and tools
        try:
            # Create sheet context summary
            summary = sheet_summary(sheet)
            ctx = f"[Context] Active sheet '{summary['name']}' has {summary['n_rows']} rows × {summary['n_cols']} cols; Headers: {summary['headers']}."
            print(f"[{request_id}] 📊 Sheet context: {ctx}")
            
            # Import and initialize orchestrator
            print(f"[{request_id}] 🎯 Importing orchestrator...")
            from agents.orchestrator import Orchestrator
            print(f"[{request_id}] 🎯 Creating orchestrator with {len(tool_functions)} tool functions")
            print(f"[{request_id}] 🔧 Available tools: {list(tool_functions.keys())}")
            
            orchestrator = Orchestrator(
                llm=llm_client,
                sheet=sheet,
                tool_functions=tool_functions
            )
            print(f"[{request_id}] ✅ Orchestrator created successfully")

            # Notify client that the assistant has started processing
            print(f"[{request_id}] 📡 Sending start event to client")
            yield { 'type': 'start' }
            
            # List to collect updates that may happen during streaming
            collected_updates = []
            
            # Start streaming
            print(f"[{request_id}] 🔄 Starting streaming with orchestrator, mode={mode}")
            print(f"[{request_id}] 📚 History length: {len(history)} messages")
            content_buffer = ""
            chunk_count = 0
            
            # Stream the orchestrator's response
            print(f"[{request_id}] 🚀 Calling orchestrator.stream_run...")
            async for chunk in orchestrator.stream_run(mode, message, history):
                chunk_count += 1
                print(f"[{request_id}] 📦 Received chunk #{chunk_count}: {type(chunk)} - {str(chunk)[:100]}{'...' if len(str(chunk)) > 100 else ''}")
                # Convert string chunks to ChatStep for compatibility
                if isinstance(chunk, str):
                    # Convert string chunks to ChatStep for compatibility
                    content_buffer += chunk
                    yield {"type": "chunk", "text": chunk}
                else:
                    # Handle ChatStep objects
                    if hasattr(chunk, "role") and chunk.role == "assistant" and hasattr(chunk, "content") and chunk.content:
                        # Format the text chunk and stream it
                        content_buffer += chunk.content
                        yield {"type": "chunk", "text": chunk.content}
                    elif hasattr(chunk, "role") and chunk.role == "tool" and hasattr(chunk, "toolResult"):
                        # For tool results, we stream an indicator and trigger UI update
                        tool_result = chunk.toolResult
                        
                        # Check both toolCall and toolcall properties (case-sensitivity check)
                        tool_call = None
                        if hasattr(chunk, "toolCall"):
                            tool_call = chunk.toolCall
                        elif hasattr(chunk, "toolcall"):
                            tool_call = chunk.toolcall
                        
                        # Get the tool name safely
                        tool_name = "unknown-tool"
                        if tool_call and hasattr(tool_call, "name"):
                            tool_name = tool_call.name
                        
                        # Skip read-only operations
                        if tool_name not in {"get_cell", "get_range"}:
                            # If it's an update type tool, add it to collected updates
                            if isinstance(tool_result, dict):
                                if "updates" in tool_result:
                                    # Send each cell update as its own event instead of batching
                                    for update in tool_result["updates"]:
                                        collected_updates.append(update)
                                        yield {"type": "update", "payload": update}
                                elif "cell" in tool_result:  # Single cell operation
                                    collected_updates.append(tool_result)
                                    yield {"type": "update", "payload": tool_result}
                                else:
                                    # For other tool results without specific cell updates, send as is
                                    yield {"type": "update", "payload": tool_result}
            
            # Save conversation history (optimistic, we have a complete response)
            if content_buffer:
                add_to_history(history_key, "user", message)
                add_to_history(history_key, "assistant", content_buffer)
            
            # End with the final sheet state
            sheet_output = sheet.to_dict()
            yield {"type": "complete", "sheet": sheet_output}
            
        except Exception as e:
            print(f"[{request_id}] ❌ Error in streaming: {str(e)}")
            traceback.print_exc()
            yield {"type": "chunk", "text": f"\n\nError: {str(e)}"}
            
    except Exception as e:
        print(f"[{request_id}] ❌ Error setting up streaming: {str(e)}")
        traceback.print_exc()
        yield {"type": "chunk", "text": f"Error: {str(e)}"} 