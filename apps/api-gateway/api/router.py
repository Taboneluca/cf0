import asyncio
import time
import traceback
import os
from typing import Dict, Any, Optional, AsyncGenerator
from functools import partial
import json  # for serializing sheet state
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
        def set_cell_with_xref(cell_ref: str = None, cell: str = None, value: Any = None, **kwargs):
            # Accept either cell_ref or cell parameter name
            ref = cell_ref if cell_ref is not None else cell
            if ref is None:
                print(f"[{request_id}] ⚠️ Missing cell reference in set_cell call")
                return {"error": "Missing cell reference parameter"}
            
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
            return set_cell(ref, value, sheet=target_sheet)
        
        # Function to handle set_cells with cross-sheet references
        def set_cells_with_xref(updates: list[dict[str, Any]] = None, cells_dict: dict[str, Any] = None, **kwargs):
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
            
            for update in updates:
                # Skip invalid update objects
                if not isinstance(update, dict) or "cell" not in update:
                    continue
                    
                cell_ref = update["cell"]
                value = update.get("value", update.get("new_value", update.get("new", None)))
                
                # If the cell reference includes a sheet name (e.g., Sheet2!A1)
                if "!" in cell_ref:
                    sheet_name, ref = cell_ref.split("!", 1)
                    sheet_updates[sheet_name].append({"cell": ref, "value": value})
                else:
                    sheet_updates[sid].append({"cell": cell_ref, "value": value})
            
            # Apply updates to each sheet
            for target_sid, sheet_updates_list in sheet_updates.items():
                try:
                    target_sheet = workbook.sheet(target_sid)
                    if not target_sheet:
                        results.append({"error": f"Sheet {target_sid} not found"})
                        continue
                        
                    for update in sheet_updates_list:
                        result = set_cell(update["cell"], update["value"], sheet=target_sheet)
                        # Add sheet information to the result
                        result["sheet_id"] = target_sid
                        results.append(result)
                except Exception as e:
                    results.append({"error": f"Error updating sheet {target_sid}: {str(e)}"})
            
            # Return a new empty update if results is still empty (avoid errors)
            if not results:
                results.append({"cell": "A1", "new_value": "", "kind": "no_change"})
                
            return {"updates": results}
        
        # Function to apply batch updates and generate a final reply in one step
        def apply_updates_and_reply(updates: list[dict[str, Any]] = None, reply: str = None, **kwargs):
            if updates is None:
                updates = []
                
            if not reply:
                reply = "Updates applied."
                
            # Apply the updates
            result = set_cells_with_xref(updates=updates)
            
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
    print(f"[{request_id}] 🔄 process_message_streaming: mode={mode}, wid={wid}, sid={sid}")
    
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
        def set_cell_with_xref(cell_ref: str = None, cell: str = None, value: Any = None, **kwargs):
            # Accept either cell_ref or cell parameter name
            ref = cell_ref if cell_ref is not None else cell
            if ref is None:
                print(f"[{request_id}] ⚠️ Missing cell reference in set_cell call")
                return {"error": "Missing cell reference parameter"}
            
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
            return set_cell(ref, value, sheet=target_sheet)
        
        # Function to handle set_cells with cross-sheet references - same as process_message
        def set_cells_with_xref(updates: list[dict[str, Any]] = None, cells_dict: dict[str, Any] = None, **kwargs):
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
            
            for update in updates:
                # Skip invalid update objects
                if not isinstance(update, dict) or "cell" not in update:
                    continue
                    
                cell_ref = update["cell"]
                value = update.get("value", update.get("new_value", update.get("new", None)))
                
                # If the cell reference includes a sheet name (e.g., Sheet2!A1)
                if "!" in cell_ref:
                    sheet_name, ref = cell_ref.split("!", 1)
                    sheet_updates[sheet_name].append({"cell": ref, "value": value})
                else:
                    sheet_updates[sid].append({"cell": cell_ref, "value": value})
            
            # Apply updates to each sheet
            for target_sid, sheet_updates_list in sheet_updates.items():
                try:
                    target_sheet = workbook.sheet(target_sid)
                    if not target_sheet:
                        results.append({"error": f"Sheet {target_sid} not found"})
                        continue
                        
                    for update in sheet_updates_list:
                        result = set_cell(update["cell"], update["value"], sheet=target_sheet)
                        # Add sheet information to the result
                        result["sheet_id"] = target_sid
                        results.append(result)
                except Exception as e:
                    results.append({"error": f"Error updating sheet {target_sid}: {str(e)}"})
            
            # Return a new empty update if results is still empty (avoid errors)
            if not results:
                results.append({"cell": "A1", "new_value": "", "kind": "no_change"})
                
            return {"updates": results}
        
        # Function to apply batch updates and generate a final reply in one step
        def apply_updates_and_reply(updates: list[dict[str, Any]] = None, reply: str = None, **kwargs):
            if updates is None:
                updates = []
                
            if not reply:
                reply = "Updates applied."
                
            # Apply the updates
            result = set_cells_with_xref(updates=updates)
            
            # Add our reply
            result["reply"] = reply
            
            return result
        
        # Create a streaming wrapper for tool functions
        def create_streaming_wrapper(tool_fn, name):
            """Create a wrapper that logs the call"""
            def wrapper(*args, **kwargs):
                print(f"[{request_id}] 🔧 Streaming tool call: {name}")
                result = tool_fn(*args, **kwargs)
                return result
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
            else:
                # Use default model from environment
                llm_client = get_default_client()
                print(f"[{request_id}] 🔄 Using default model: {llm_client.model}")
        except Exception as e:
            print(f"[{request_id}] ❌ Error initializing LLM client: {e}")
            yield {"error": f"Error initializing LLM client: {e}"}
            return
        
        # Initialize the orchestrator with the LLM client and tools
        try:
            # Create sheet context summary
            summary = sheet_summary(sheet)
            ctx = f"[Context] Active sheet '{summary['name']}' has {summary['n_rows']} rows × {summary['n_cols']} cols; Headers: {summary['headers']}."
            
            # Import and initialize orchestrator
            from agents.orchestrator import Orchestrator
            orchestrator = Orchestrator(
                llm=llm_client,
                sheet=sheet,
                tool_functions=tool_functions
            )

            # Notify client that the assistant has started processing
            yield { 'type': 'start' }
            
            # List to collect updates that may happen during streaming
            collected_updates = []
            
            # Start streaming
            print(f"[{request_id}] 🔄 Starting streaming with orchestrator, mode={mode}")
            content_buffer = ""
            
            # Stream the orchestrator's response
            async for chunk in orchestrator.stream_run(mode, message, history):
                # Guard for strings - handle both string content and ChatStep objects
                if isinstance(chunk, str):
                    # Format the text chunk and stream it
                    content_buffer += chunk
                    yield {"type": "chunk", "text": chunk}
                elif hasattr(chunk, "role") and chunk.role == "assistant" and hasattr(chunk, "content") and chunk.content:
                    # Format the text chunk and stream it
                    content_buffer += chunk.content
                    yield {"type": "chunk", "text": chunk.content}
                elif hasattr(chunk, "role") and chunk.role == "tool" and hasattr(chunk, "toolResult"):
                    # For tool results, we stream an indicator and trigger UI update
                    tool_result = chunk.toolResult
                    tool_name = getattr(chunk.toolCall, "name", "unknown-tool") if hasattr(chunk, "toolCall") else "unknown-tool"
                    
                    # Skip read-only operations
                    if tool_name not in {"get_cell", "get_range"}:
                        # If it's an update type tool, add it to collected updates
                        if isinstance(tool_result, dict):
                            if "updates" in tool_result:
                                collected_updates.extend(tool_result["updates"])
                            elif "cell" in tool_result:  # Single cell operation
                                collected_updates.append(tool_result)
                            
                            # Stream the update info to client for live updates
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