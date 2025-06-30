from fastapi import FastAPI, HTTPException, Request, Response, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union, AsyncGenerator
import os
import asyncio
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

# Direct imports instead of core.* to fix deployment issues
from spreadsheet_engine.model import Spreadsheet
from spreadsheet_engine.operations import (
    get_cell, get_range, summarize_sheet, calculate,
    set_cell, add_row, add_column, delete_row, delete_column,
    sort_range, find_replace, create_new_sheet,
    get_row_by_header, get_column_by_header,
    apply_scalar_to_row, apply_scalar_to_column, set_cells,
    list_sheets, get_sheet_summary
)
from spreadsheet_engine.summary import sheet_summary

# Default values for sheet creation
DEFAULT_ROWS = 100
DEFAULT_COLS = 26

from workbook_store import get_sheet, get_workbook, workbooks, initialize as initialize_workbook_store
from api.router import process_message, process_message_streaming
from api.schemas import ChatRequest, ChatResponse
from llm.factory import get_client, get_default_client  # Direct import instead of core.llm
from llm.catalog import get_models, get_model_info  # Direct import
from llm import PROVIDERS  # Import the provider registry
from api.memory import clear_history, get_history
from agents.base_agent import ChatStep  # Direct import instead of core.agents
from agents.ask_agent import build as build_ask_agent  # Direct import
from agents.analyst_agent import build as build_analyst_agent  # Direct import
from api.admin_prompts import router as prompts_admin_router
import json
from fastapi.responses import StreamingResponse
import time
import traceback
from functools import partial
from langserve import add_routes  # NEW
from langchain.schema.runnable import RunnableGenerator  # NEW

# Load environment variables
load_dotenv()

# Initialize Sentry
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.2,
)

# Initialize FastAPI app
app = FastAPI(title="Intelligent Spreadsheet Assistant")

# Add compression middleware for large responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include the prompts admin router
app.include_router(prompts_admin_router)

# Add RequestValidationError handler for debugging 422 errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for RequestValidationError to capture and log detailed validation failures.
    This helps identify the exact cause of 422 errors by logging the request body and validation error details.
    """
    # Get request body for logging
    try:
        request_body = await request.body()
        request_body_str = request_body.decode('utf-8')
    except Exception:
        request_body_str = "Could not decode request body"
    
    # Log detailed validation error information
    print(f"🚨 RequestValidationError on {request.method} {request.url}")
    print(f"📄 Request body: {request_body_str}")
    print(f"❌ Validation errors: {exc.errors()}")
    print(f"🔍 Error details: {str(exc)}")
    
    # Return detailed JSON response with validation error information
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "body": request_body_str,
            "message": "Request validation failed - check logs for details"
        }
    )

@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on startup"""
    # Start the Supabase persistence worker
    await initialize_workbook_store()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class SheetUpdateRequest(BaseModel):
    cell: str  # e.g., "A1" or "Sheet2!A1"
    value: Any  # Value to set

class NewSheetRequest(BaseModel):
    name: Optional[str] = None
    rows: Optional[int] = 30
    columns: Optional[int] = 10

# Create a semaphore to limit concurrent LLM requests
llm_concurrency = int(os.getenv("LLM_CONCURRENCY", "5"))
chat_limiter = asyncio.Semaphore(llm_concurrency)

# Root route for API check
@app.get("/")
async def root():
    return {"status": "Intelligent Spreadsheet Assistant API is running"}

# Dedicated health check endpoint
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring systems.
    Returns a 200 OK response if the service is healthy.
    """
    return {
        "status": "healthy",
        "version": os.environ.get("APP_VERSION", "development")
    }

# Get available models endpoint
@app.get("/models")
async def available_models():
    """
    Return a list of all available language models with their capabilities.
    This is used by the frontend to populate the model selector.
    """
    return get_models()

# Get the workbook sheet data
@app.get("/workbook/{wid}/sheet/{sid}")
async def get_sheet_endpoint(wid: str, sid: str):
    """Get the state of a specific sheet in a workbook"""
    sheet = get_sheet(wid, sid)
    wb = get_workbook(wid)
    return {
        "sheet": sheet.to_dict(),
        "sheets": wb.list_sheets(),
        "active": sid
    }

# Get all sheets in a workbook
@app.get("/workbook/{wid}/sheets")
async def get_workbook_sheets(wid: str):
    """Get all sheets in a workbook"""
    wb = get_workbook(wid)
    return {
        "sheets": wb.list_sheets(),
        "active": wb.active
    }

# Update a specific sheet in a workbook
@app.post("/workbook/{wid}/sheet/{sid}/update")
async def update_sheet(request: SheetUpdateRequest, wid: str, sid: str):
    """Update a specific cell in a sheet"""
    try:
        # Handle cross-sheet references
        cell_ref = request.cell
        target_sid = sid
        
        # If the cell reference includes a sheet name (e.g., Sheet2!A1)
        if "!" in cell_ref:
            parts = cell_ref.split("!", 1)
            target_sid = parts[0]  # Extract sheet name
            cell_ref = parts[1]    # Extract cell reference
            
        sheet = get_sheet(wid, target_sid)
        result = set_cell(cell_ref, request.value, sheet)
        
        # Ensure the response has 'new' instead of 'new_value' for consistency
        if 'new_value' in result and 'new' not in result:
            result['new'] = result['new_value']
        
        # Get workbook to return all sheets
        wb = get_workbook(wid)
        
        # Add all sheets data to the response
        result.update({
            "sheet": sheet.to_dict(),
            "all_sheets": {
                name: s.to_dict()
                for name, s in wb.all_sheets().items()
            },
            "active": target_sid
        })
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Create a new sheet in a workbook
@app.post("/workbook/{wid}/sheet")
async def create_sheet(request: NewSheetRequest = None, wid: str = "default"):
    """Create a new sheet in a workbook"""
    wb = get_workbook(wid)
    name = f"Sheet{len(wb.sheets)+1}" if not request or not request.name else request.name
    try:
        new_sheet = wb.new_sheet(name)
        return {
            "sheets": wb.list_sheets(),
            "active": name,
            "sheet": new_sheet.to_dict()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Chat endpoint - main interaction
@app.post("/chat", include_in_schema=False)
async def chat_deprecated(_: ChatRequest):
    """Legacy blocking chat endpoint removed."""
    raise HTTPException(status_code=410, detail="Deprecated – use /ask/invoke or /analyst/invoke.")

# Chat endpoint with streaming support
@app.post("/chat/stream", include_in_schema=False)
async def stream_chat_deprecated(_: ChatRequest):
    raise HTTPException(status_code=410, detail="Deprecated – use /ask/stream or /analyst/stream.")

# Keep old endpoints for backwards compatibility but mark as deprecated
@app.get("/sheet", deprecated=True)
async def get_sheet_endpoint_old(session_id: str = "default"):
    """
    Get the current state of the spreadsheet
    
    DEPRECATED: Use /workbook/{wid}/sheet/{sid} instead
    """
    sheet = get_sheet("default", "Sheet1")
    return {
        "sheet": sheet.to_dict()
    }

@app.post("/sheet/update", deprecated=True)
async def update_sheet_old(request: SheetUpdateRequest, session_id: str = "default"):
    """
    Update a specific cell in the spreadsheet
    
    DEPRECATED: Use /workbook/{wid}/sheet/{sid}/update instead
    """
    try:
        sheet = get_sheet("default", "Sheet1")
        result = set_cell(request.cell, request.value, sheet)
        # Ensure the response has 'new' instead of 'new_value' for consistency
        if 'new_value' in result and 'new' not in result:
            result['new'] = result['new_value']
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/sheet/new", deprecated=True)
async def new_sheet_old(request: NewSheetRequest = None, session_id: str = "default"):
    """
    Create a new spreadsheet
    
    DEPRECATED: Use /workbook/{wid}/sheet instead
    """
    rows = DEFAULT_ROWS if not request or not request.rows else request.rows
    columns = DEFAULT_COLS if not request or not request.columns else request.columns
    wb = get_workbook("default")
    wb.new_sheet("Sheet1")
    
    # Clear conversation history for this session when creating a new sheet
    clear_history(session_id)
    
    return {
        "action": "new_sheet",
        "name": "Sheet1",
        "rows": rows,
        "columns": columns
    }

@app.post("/session/reset", deprecated=True)
async def reset_session(session_id: str = "default"):
    """Reset conversation history for a specific session"""
    clear_history(session_id)
    return {"status": "success"}

# Add a delete endpoint for workbooks
@app.delete("/workbook/{wid}")
async def delete_workbook(wid: str):
    """Delete a workbook and all its sheets"""
    try:
        # Safely remove from memory (no error if missing)
        workbooks.pop(wid, None)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add this new endpoint after the existing endpoints
@app.get("/debug/config")
async def debug_config():
    """Get information about the current configuration."""
    return {
        "spreadsheet_engine": "Direct imports - deployment ready",
        "environment": {
            "USE_DATAFRAME_MODEL": os.getenv("USE_DATAFRAME_MODEL", "0"),
            "USE_FORMULA_ENGINE": os.getenv("USE_FORMULA_ENGINE", "0"),
            "USE_INCREMENTAL_RECALC": os.getenv("USE_INCREMENTAL_RECALC", "1"),
            "MAX_TOOL_ITERATIONS": os.getenv("MAX_TOOL_ITERATIONS", "50"),
            "MODEL": os.getenv("OPENAI_MODEL", "gpt-4o")
        },
        "versions": {
            "pandas": __import__("pandas").__version__,
            "numpy": __import__("numpy").__version__
        }
    }

@app.get("/workbook/{wid}/sheet/{sid}/range")
async def get_sheet_range(wid: str, sid: str, start: int = 0, end: int = 20):
    """
    Get a range of rows from a sheet, useful for virtualized UI
    """
    try:
        sheet = get_sheet(wid, sid)
        # Ensure start and end are within bounds
        start = max(0, min(start, sheet.n_rows-1))
        end = max(start+1, min(end, sheet.n_rows))
        
        # Extract the rows in the requested range
        rows = sheet.cells[start:end]
        
        return {
            "start": start,
            "end": end,
            "rows": rows,
            "total_rows": sheet.n_rows,
            "total_cols": sheet.n_cols
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket endpoint for debug mode - step-by-step agent execution
@app.websocket("/chat/step")
async def chat_step(ws: WebSocket):
    await ws.accept()
    try:
        # first message from frontend is identical to ChatRequest JSON
        data = await ws.receive_json()
        req = ChatRequest(**data)

        # get the sheet and workbook
        sheet = get_sheet(req.wid, req.sid)
        if not sheet:
            await ws.send_json({"error": f"Sheet {req.sid} not found in workbook {req.wid}"})
            return
            
        workbook = get_workbook(req.wid)
        if not workbook:
            await ws.send_json({"error": f"Workbook {req.wid} not found"})
            return
            
        # Create workbook metadata
        all_sheets_data = {name: sheet_summary(s) for name, s in workbook.all_sheets().items()}
        workbook_metadata = {
            "sheets": workbook.list_sheets(),
            "active": req.sid,
            "all_sheets_data": all_sheets_data
        }
        
        # Add contexts if provided
        if req.contexts:
            workbook_metadata["contexts"] = req.contexts

        # build llm_client based on model parameter
        if req.model:
            llm_client = get_client(req.model)
        else:
            llm_client = get_default_client()

        # Get tool functions with sheet access
        tool_functions = {}
        
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
                    sheet_updates[req.sid].append({"cell": cell_ref, "value": value})
            
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
            
        # Helper for accepting both cell_ref and cell param names
        def _wrap_get_cell(get_cell_fn, sheet):
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
            
        # Prepare wrapped functions that have access to the sheet
        tool_functions["get_cell"] = _wrap_get_cell(get_cell, sheet)
        tool_functions["get_range"] = _wrap_get_range(get_range, sheet)
        tool_functions["calculate"] = _wrap_calculate(calculate, sheet)
        tool_functions["sheet_summary"] = partial(summarize_sheet, sheet=sheet)
        tool_functions["set_cell"] = set_cell_with_xref
        tool_functions["set_cells"] = set_cells_with_xref
        tool_functions["add_row"] = partial(add_row, sheet=sheet)
        tool_functions["add_column"] = partial(add_column, sheet=sheet)
        tool_functions["delete_row"] = partial(delete_row, sheet=sheet)
        tool_functions["delete_column"] = partial(delete_column, sheet=sheet)
        tool_functions["sort_range"] = partial(sort_range, sheet=sheet)
        tool_functions["find_replace"] = partial(find_replace, sheet=sheet)
        tool_functions["get_row_by_header"] = partial(get_row_by_header, sheet=sheet)
        tool_functions["get_column_by_header"] = partial(get_column_by_header, sheet=sheet)
        tool_functions["apply_scalar_to_row"] = partial(apply_scalar_to_row, sheet=sheet)
        tool_functions["apply_scalar_to_column"] = partial(apply_scalar_to_column, sheet=sheet)
        
        # Get workbook-level functions
        tool_functions["create_new_sheet"] = partial(create_new_sheet, workbook=workbook)
        tool_functions["list_sheets"] = partial(list_sheets, workbook=workbook)
        tool_functions["get_sheet_summary"] = partial(get_sheet_summary, workbook=workbook)
        
        # Create the agent with the appropriate tool functions
        agent = build_analyst_agent(llm=llm_client) \
                if req.mode == "analyst" else build_ask_agent(llm=llm_client)
        
        # Inject tool functions specific to this session
        agent = agent.clone_with_tools(tool_functions)
        
        # Run the agent and stream step-by-step results
        history = get_history(req.wid)
        async for step in agent.run_iter(req.message, history):
            await ws.send_json(step.model_dump())
            
        # Send a final "complete" message 
        await ws.send_json({"status": "complete"})
        
    except WebSocketDisconnect:
        print("WebSocket disconnected")
        return
    except Exception as e:
        print(f"Error in chat_step: {str(e)}")
        traceback.print_exc()
        await ws.send_json({"error": str(e)})
        await ws.close()

# Add this after the existing endpoints

class ApplyUpdatesRequest(BaseModel):
    updates: List[Dict[str, Any]]

@app.post("/workbook/{wid}/sheet/{sid}/apply")
async def apply_updates(request: ApplyUpdatesRequest, wid: str, sid: str):
    """Apply a batch of cell updates to a sheet"""
    try:
        # Get the workbook and sheet
        wb = get_workbook(wid)
        sheet = wb.sheet(sid)
        
        if not sheet:
            raise HTTPException(status_code=404, detail=f"Sheet {sid} not found")
        
        # Define a function to handle cross-sheet references
        def set_cells_with_xref(updates: list[dict[str, Any]]):
            from collections import defaultdict
            results = []
            
            # Check for empty updates
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
                    target_sheet = wb.sheet(target_sid)
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
            
            return {"updates": results}
        
        # Apply the updates
        result = set_cells_with_xref(request.updates)
        
        # Clear cached snapshot – changes are now accepted
        from chat.router import PENDING_STORE
        PENDING_STORE.pop((wid, sid), None)
        
        # Return the updated sheet and results
        return {
            "status": "success",
            "result": result,
            "sheet": sheet.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workbook/{wid}/sheet/{sid}/reject")
async def reject_updates(wid: str, sid: str):
    """Roll back all optimistic updates that were streamed but not applied."""
    try:
        from chat.router import PENDING_STORE
        
        key = (wid, sid)
        snap = PENDING_STORE.pop(key, None)
        if snap is None:
            raise HTTPException(404, "Nothing to reject")
            
        # Replace the live sheet contents with the snapshot
        wb = get_workbook(wid)
        if not wb:
            raise HTTPException(404, f"Workbook {wid} not found")
            
        # Replace the sheet in the workbook with our snapshot
        wb._sheets[sid] = snap  # low-level swap; keep same object key
        
        return {
            "status": "reverted",
            "sheet": snap.to_dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ================================================================================
# LANGSERVE INTEGRATION - Enhanced streaming with LangServe
# ================================================================================

# LangServe request/response models  
class LangServeRequest(BaseModel):
    mode: str
    message: str
    wid: str = "default"
    sid: str = "Sheet1"
    contexts: List[str] = []
    model: Optional[str] = None

class LangServeInputWrapper(BaseModel):
    """
    LangServe-compatible request wrapper that handles the input field requirement.
    LangServe expects all parameters to be nested under an 'input' field.
    """
    input: LangServeRequest

class LangServeResponse(BaseModel):
    content: str
    metadata: Dict[str, Any] = {}

# LangServe streaming wrapper that uses the existing process_message_streaming
async def langserve_stream_wrapper(request: Union[LangServeRequest, LangServeInputWrapper]) -> AsyncGenerator[str, None]:
    """
    LangServe wrapper that leverages the existing robust streaming infrastructure.
    Enhanced to ensure proper SSE format compliance with explicit start and complete events.
    Supports both direct LangServeRequest and wrapped LangServeInputWrapper formats.
    """
    try:
        # Extract the actual request from the input wrapper if needed
        if isinstance(request, LangServeInputWrapper):
            actual_request = request.input
            print(f"🔄 Extracted request from LangServe input wrapper: {actual_request.model_dump()}")
        else:
            actual_request = request
            print(f"📝 Using direct LangServe request: {actual_request.model_dump()}")
        
        # Get workbook and sheet using the extracted request
        wb = get_workbook(actual_request.wid)
        if not wb:
            error_event = {"type": "error", "error": f"Workbook {actual_request.wid} not found"}
            yield f"data: {json.dumps(error_event)}\n\n"
            return
            
        sheet = wb.sheet(actual_request.sid)
        if not sheet:
            error_event = {"type": "error", "error": f"Sheet {actual_request.sid} not found in workbook {actual_request.wid}"}
            yield f"data: {json.dumps(error_event)}\n\n"
            return
        
        # Create workbook metadata
        all_sheets_data = {
            name: s.to_dict() for name, s in wb.all_sheets().items()
        }
        
        workbook_metadata = {
            "sheets": wb.list_sheets(),
            "active": actual_request.sid,
            "all_sheets_data": all_sheets_data,
            "contexts": actual_request.contexts
        }
        
        # Yield explicit start event
        start_event = {"type": "start"}
        yield f"data: {json.dumps(start_event)}\n\n"
        
        # Use the existing process_message_streaming function
        async for chunk in process_message_streaming(
            actual_request.mode,
            actual_request.message,
            actual_request.wid,
            actual_request.sid,
            sheet,
            workbook_metadata,
            actual_request.model
        ):
            try:
                if isinstance(chunk, dict):
                    # Map legacy dicts to our unified wire format expected by frontend
                    if "type" in chunk and chunk["type"] == "chunk" and "text" in chunk:
                        payload = {"type": "chunk", "text": chunk["text"]}
                        yield f"data: {json.dumps(payload)}\n\n"
                    elif "text" in chunk:
                        payload = {"type": "chunk", "text": chunk["text"]}
                        yield f"data: {json.dumps(payload)}\n\n"
                    elif "type" in chunk:
                        # forward other structured events as-is in proper SSE format
                        yield f"data: {json.dumps(chunk)}\n\n"
                    else:
                        # Default handling for other dict types
                        yield f"data: {json.dumps(chunk)}\n\n"
                elif isinstance(chunk, str):
                    payload = {"type": "chunk", "text": chunk}
                    yield f"data: {json.dumps(payload)}\n\n"
                else:
                    # Handle other data types
                    payload = {"type": "chunk", "text": str(chunk)}
                    yield f"data: {json.dumps(payload)}\n\n"
            except Exception as chunk_error:
                # Handle errors in chunk processing
                error_event = {"type": "error", "error": f"Error processing chunk: {str(chunk_error)}"}
                yield f"data: {json.dumps(error_event)}\n\n"
        
        # Yield explicit complete event
        complete_event = {"type": "complete"}
        yield f"data: {json.dumps(complete_event)}\n\n"
                
    except Exception as e:
        # Yield properly formatted error event
        error_event = {"type": "error", "error": str(e)}
        yield f"data: {json.dumps(error_event)}\n\n"

# LangServe invoke wrapper
async def langserve_invoke_wrapper(request: Union[LangServeRequest, LangServeInputWrapper]) -> LangServeResponse:
    """LangServe invoke wrapper for blocking responses"""
    # Extract the actual request for metadata
    actual_request = request.input if isinstance(request, LangServeInputWrapper) else request
    
    content_parts = []
    async for chunk in langserve_stream_wrapper(request):
        try:
            # chunk is JSON string
            data = json.loads(chunk)
            if isinstance(data, dict) and data.get("type") == "chunk":
                content_parts.append(data.get("text", ""))
        except Exception:
            # fallback raw
            content_parts.append(str(chunk))
    
    return LangServeResponse(
        content="".join(content_parts),
        metadata={"mode": actual_request.mode, "wid": actual_request.wid, "sid": actual_request.sid}
    )

# ================================================================================
# LANGSERVE ROUTE REGISTRATION (NO LEGACY FALLBACK)
# ================================================================================

# Helper to build runnable that supports both invoke and stream
def build_runnable():
    async def _stream(req: Union[LangServeRequest, LangServeInputWrapper]):
        async for chunk in langserve_stream_wrapper(req):
            yield chunk

    return RunnableGenerator(_stream).with_types(
        input_type=LangServeInputWrapper,  # Use wrapper type for LangServe compatibility
        output_type=LangServeResponse,
    )

ask_runnable = build_runnable()
analyst_runnable = build_runnable()

# Register routes – mounted at /ask and /analyst (invoke + stream endpoints only)
add_routes(
    app,
    ask_runnable,
    path="/ask",
    enabled_endpoints=["invoke", "stream"],
)

add_routes(
    app,
    analyst_runnable,
    path="/analyst",
    enabled_endpoints=["invoke", "stream"],
)

# Generic combined route (if needed) under /langserve using ask_runnable (acts as default)
add_routes(
    app,
    ask_runnable,
    path="/langserve",
    enabled_endpoints=["invoke", "stream"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 