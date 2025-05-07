import asyncio
import time
import traceback
from typing import Dict, Any, Optional, AsyncGenerator
from functools import partial
import json  # for serializing sheet state

from agents.ask_agent import AskAgent
from agents.analyst_agent import AnalystAgent
from spreadsheet_engine.model import Spreadsheet
from spreadsheet_engine.summary import sheet_summary
from workbook_store import get_sheet, get_workbook
from chat.memory import get_history, add_to_history

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
    start_time = time.time()
    request_id = f"pm-{int(start_time*1000)}"
    print(f"[{request_id}] 🔄 process_message: mode={mode}, wid={wid}, sid={sid}")
    
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
            
            # Schedule recalculation to happen asynchronously
            try:
                asyncio.create_task(workbook.recalculate())
                print(f"[{request_id}] 🔄 Scheduled async recalculation")
            except Exception as e:
                print(f"[{request_id}] ⚠️ Error scheduling recalculation: {e}")
            
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
            # --- NEW single-shot tool -----------------------------------
            "apply_updates_and_reply": lambda updates=None, reply="", **kw: (
                (lambda _res: {**_res, "reply": reply})(
                    set_cells_with_xref(updates=updates)
                )
            ),
            # New workbook-level tools
            "list_sheets": partial(list_sheets, wid=wid),
            "get_sheet_summary": lambda sid: get_sheet_summary(sid, wid=wid),
            "switch_sheet": lambda new_sid: {"status": "switched", "sheet": workbook.sheet(new_sid).to_dict()},
        }
        
        # Track updates made to the sheet
        collected_updates = []
        
        # Update the tool functions in the agents
        print(f"[{request_id}] 🤖 Creating agent for mode: {mode}")
        agent_start = time.time()
        
        if mode == "ask":
            # Clone the agent with updated tool functions
            agent = AskAgent.clone_with_tools(tools)
            # Add cross-sheet instructions
            agent.add_system_message(system_context)
            print(f"[{request_id}] 🚀 Running AskAgent with message length: {len(message)}")
            result = await agent.run(message, history)
        elif mode == "analyst":
            # Clone the agent with updated tool functions
            agent = AnalystAgent.clone_with_tools(tools)
            # Add cross-sheet instructions
            agent.add_system_message(system_context)
            print(f"[{request_id}] 🚀 Running AnalystAgent with message length: {len(message)}")
            result = await agent.run(message, history)
            
            # Collect the updates made during the agent's execution
            if "updates" in result:
                collected_updates = result["updates"]
                print(f"[{request_id}] 📊 Collected {len(collected_updates)} updates from agent")
        else:
            print(f"[{request_id}] ❌ Invalid mode: {mode}")
            return {
                "reply": f"Invalid mode: {mode}. Please use 'ask' or 'analyst'.", 
                "sheet": sheet.to_dict(),
                "log": []
            }
        
        agent_time = time.time() - agent_start
        print(f"[{request_id}] ⏱️ Agent completed in {agent_time:.2f}s with reply length: {len(result['reply'])}")
        
        # Store the user message and assistant's reply in conversation history
        add_to_history(history_key, "user", message)
        add_to_history(history_key, "assistant", result["reply"])
        
        process_time = time.time() - start_time
        print(f"[{request_id}] ✅ process_message completed in {process_time:.2f}s")
        
        # Return the reply, updated sheet state, and log of changes
        return {
            "reply": result["reply"], 
            "sheet": sheet.optimized_to_dict(max_rows=100, max_cols=30),
            "all_sheets": {name: s.optimized_to_dict(max_rows=100, max_cols=30) for name, s in workbook.all_sheets().items()},
            "log": collected_updates
        }
    except Exception as e:
        total_time = time.time() - start_time
        print(f"[{request_id}] ❌ Error in process_message after {total_time:.2f}s: {str(e)}")
        traceback.print_exc()
        raise 

async def process_message_streaming(
    mode: str, 
    message: str, 
    wid: str, 
    sid: str, 
    sheet=None, 
    workbook_metadata: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Streaming version of process_message that yields incremental updates.
    
    Args:
        mode: The agent mode ("ask" or "analyst")
        message: The user message to process
        wid: Workbook ID
        sid: Sheet ID in the workbook
        sheet: The spreadsheet to use (if None, uses get_sheet(wid, sid))
        workbook_metadata: Additional metadata about the workbook and its sheets
        
    Yields:
        Dict with incremental reply chunks and status updates
    """
    start_time = time.time()
    request_id = f"stream-{int(start_time*1000)}"
    print(f"[{request_id}] 🔄 process_message_streaming: mode={mode}, wid={wid}, sid={sid}")
    
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
            
            # Schedule recalculation to happen asynchronously
            try:
                asyncio.create_task(workbook.recalculate())
                print(f"[{request_id}] 🔄 Scheduled async recalculation")
            except Exception as e:
                print(f"[{request_id}] ⚠️ Error scheduling recalculation: {e}")
            
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
            # --- NEW single-shot tool -----------------------------------
            "apply_updates_and_reply": lambda updates=None, reply="", **kw: (
                (lambda _res: {**_res, "reply": reply})(
                    set_cells_with_xref(updates=updates)
                )
            ),
            # New workbook-level tools
            "list_sheets": partial(list_sheets, wid=wid),
            "get_sheet_summary": lambda sid: get_sheet_summary(sid, wid=wid),
            "switch_sheet": lambda new_sid: {"status": "switched", "sheet": workbook.sheet(new_sid).to_dict()},
        }
        
        # Setup for streaming with tool notifications
        collected_updates = []
        
        # Yield a startup notification
        yield {"type": "start", "mode": mode}
        
        # Create tool wrappers that yield status updates
        streaming_tools = {}
        
        # Create streaming versions of the tools
        for name, tool_fn in tools.items():
            streaming_tools[name] = create_streaming_wrapper(tool_fn, name)
        
        # Handle the streaming agent run
        print(f"[{request_id}] 🤖 Creating streaming agent for mode: {mode}")
        agent_start = time.time()
        
        if mode == "ask":
            # Create an Ask agent with streaming tools
            agent = AskAgent.clone_with_tools(streaming_tools)
            agent.add_system_message(system_context)
            
            # Use the streaming run method
            print(f"[{request_id}] 🚀 Running streaming AskAgent with message length: {len(message)}")
            async for chunk in agent.stream_run(message, history):
                yield {"type": "chunk", "content": chunk}
                
            # Get the final response
            final_result = await agent.run(message, history)
            
        elif mode == "analyst":
            # Create an Analyst agent with streaming tools
            agent = AnalystAgent.clone_with_tools(streaming_tools)
            agent.add_system_message(system_context)
            
            # Use the streaming run method
            print(f"[{request_id}] 🚀 Running streaming AnalystAgent with message length: {len(message)}")
            async for chunk in agent.stream_run(message, history):
                yield {"type": "chunk", "content": chunk}
                
            # Get the final response
            final_result = await agent.run(message, history)
            
            # Collect updates
            if "updates" in final_result:
                collected_updates = final_result["updates"]
                print(f"[{request_id}] 📊 Collected {len(collected_updates)} updates from agent")
        else:
            error_msg = f"Invalid mode: {mode}. Please use 'ask' or 'analyst'."
            yield {"type": "error", "error": error_msg}
            return
        
        # Store the conversation history
        add_to_history(history_key, "user", message)
        add_to_history(history_key, "assistant", final_result["reply"])
        
        # Yield the final result
        yield {
            "type": "complete",
            "reply": final_result["reply"],
            "updates": collected_updates,
            "duration": time.time() - start_time
        }
        
        print(f"[{request_id}] ✅ Streaming process_message completed in {time.time() - start_time:.2f}s")
        
    except Exception as e:
        total_time = time.time() - start_time
        print(f"[{request_id}] ❌ Error in streaming process_message after {total_time:.2f}s: {str(e)}")
        traceback.print_exc()
        
        # Yield the error
        yield {"type": "error", "error": str(e), "duration": total_time} 