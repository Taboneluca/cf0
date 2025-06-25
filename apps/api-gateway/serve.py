from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from langserve import add_routes
import sys
import os
from typing import Dict, Any, AsyncGenerator, List, Optional
from pydantic import BaseModel
import asyncio
import time
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path to ensure relative imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import all the required modules from the existing implementation
from agents.orchestrator import Orchestrator
from llm.factory import get_client, get_default_client
from workbook_store import get_sheet, get_workbook, initialize as initialize_workbook_store
from spreadsheet_engine.model import Spreadsheet
from api.memory import get_history, add_to_history
from api.schemas import ChatRequest, ChatResponse

# ---------------------------------------------------------------------------
# FastAPI application with LangServe that exposes proper streaming endpoints
# This replaces the custom SSE implementation with LangServe's robust streaming
# /ask/stream     -> LangServe Server-Sent Events (POST JSON payload)
# /ask/invoke     -> LangServe Blocking JSON response (POST JSON payload)
# /analyst/stream -> LangServe Server-Sent Events (POST JSON payload)
# /analyst/invoke -> LangServe Blocking JSON response (POST JSON payload)
# ---------------------------------------------------------------------------

app = FastAPI(title="cf0.ai LangServe Streaming API", version="2.0.0")

# Add compression middleware for large responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on startup"""
    await initialize_workbook_store()

# Enhanced ChatRequest model with all features from main.py
class LangServeRequest(BaseModel):
    mode: str
    message: str
    wid: str = "default"
    sid: str = "Sheet1"
    contexts: List[str] = []
    model: Optional[str] = None

class LangServeResponse(BaseModel):
    content: str
    metadata: Dict[str, Any] = {}

# LangServe streaming wrapper that handles full workbook context
async def langserve_stream_wrapper(request: LangServeRequest) -> AsyncGenerator[str, None]:
    """
    Enhanced LangServe wrapper that properly handles workbook context,
    tool functions, and streaming with all the robustness of the main.py implementation
    """
    start_time = time.time()
    request_id = f"ls-stream-{int(start_time*1000)}"
    
    try:
        print(f"[{request_id}] 🚀 LangServe stream starting: mode={request.mode}, wid={request.wid}, sid={request.sid}")
        
        # Get workbook and sheet (same as main.py)
        wb = get_workbook(request.wid)
        if not wb:
            yield f"Error: Workbook {request.wid} not found"
            return
            
        sheet = wb.sheet(request.sid)
        if not sheet:
            yield f"Error: Sheet {request.sid} not found in workbook {request.wid}"
            return
        
        # Get conversation history
        history_key = request.wid
        history = get_history(history_key)
        
        # Create workbook metadata with all sheets
        all_sheets_data = {
            name: s.to_dict() for name, s in wb.all_sheets().items()
        }
        
        workbook_metadata = {
            "sheets": wb.list_sheets(),
            "active": request.sid,
            "all_sheets_data": all_sheets_data,
            "contexts": request.contexts
        }
        
        # Set up LLM client
        if request.model:
            print(f"[{request_id}] 🔄 Using explicit model: {request.model}")
            llm_client = get_client(request.model)
        else:
            llm_client = get_default_client()
            print(f"[{request_id}] 🔄 Using default model: {llm_client.model}")
        
        # Import and set up all tool functions (same as api/router.py)
        from functools import partial
        from spreadsheet_engine.operations import (
            get_cell, get_range, summarize_sheet, calculate,
            set_cell, add_row, add_column, delete_row, delete_column,
            sort_range, find_replace, create_new_sheet,
            get_row_by_header, get_column_by_header,
            apply_scalar_to_row, apply_scalar_to_column, set_cells,
            list_sheets, get_sheet_summary
        )
        
        # Tool wrapper functions (copied from api/router.py)
        def _wrap_get_cell(get_cell_fn, sheet):
            def _f(cell_ref: str = None, cell: str = None, **kw):
                return get_cell_fn(cell_ref or cell, sheet)
            return _f

        def _wrap_get_range(get_range_fn, sheet):
            def _f(range_ref: str = None, range: str = None, **kw):
                return get_range_fn(range_ref or range, sheet)
            return _f

        def _wrap_calculate(calculate_fn, sheet):
            def _f(formula: str = None, **kw):
                return calculate_fn(formula, sheet)
            return _f
        
        # Set up all tool functions
        tool_functions = {
            "get_cell": _wrap_get_cell(get_cell, sheet),
            "get_range": _wrap_get_range(get_range, sheet),
            "calculate": _wrap_calculate(calculate, sheet),
            "sheet_summary": partial(summarize_sheet, sheet=sheet),
            "set_cell": partial(set_cell, sheet=sheet),
            "set_cells": partial(set_cells, sheet=sheet),
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
            "list_sheets": partial(list_sheets, wid=request.wid),
            "get_sheet_summary": partial(get_sheet_summary, wid=request.wid),
        }
        
        # For ask mode, restrict to read-only tools
        if request.mode == "ask":
            read_only_tools = {k: v for k, v in tool_functions.items() 
                              if k in {"get_cell", "get_range", "sheet_summary", "calculate"}}
            tool_functions = read_only_tools
        
        # Create orchestrator with proper configuration
        orchestrator = Orchestrator(
            llm=llm_client,
            sheet=sheet,
            tool_functions=tool_functions
        )
        
        print(f"[{request_id}] 🎯 Starting orchestrator stream...")
        
        # Stream from orchestrator and yield content
        content_buffer = ""
        async for step in orchestrator.stream_run(request.mode, request.message, history):
            if isinstance(step, str):
                # Direct string content
                content_buffer += step
                yield step
            elif hasattr(step, 'content') and step.content:
                # ChatStep with content
                content_buffer += step.content
                yield step.content
            elif hasattr(step, 'role') and step.role == 'assistant' and hasattr(step, 'content'):
                # Assistant message
                if step.content:
                    content_buffer += step.content
                    yield step.content
        
        # Save conversation history
        if content_buffer:
            add_to_history(history_key, "user", request.message)
            add_to_history(history_key, "assistant", content_buffer)
        
        print(f"[{request_id}] ✅ LangServe stream completed in {time.time() - start_time:.2f}s")
        
    except Exception as e:
        print(f"[{request_id}] ❌ LangServe stream error: {str(e)}")
        yield f"Error: {str(e)}"

# LangServe invoke wrapper for non-streaming requests
async def langserve_invoke_wrapper(request: LangServeRequest) -> LangServeResponse:
    """
    LangServe invoke wrapper for blocking responses
    """
    content_parts = []
    async for chunk in langserve_stream_wrapper(request):
        content_parts.append(chunk)
    
    return LangServeResponse(
        content="".join(content_parts),
        metadata={"mode": request.mode, "wid": request.wid, "sid": request.sid}
    )

# Add LangServe routes for ASK mode
add_routes(
    app,
    langserve_stream_wrapper,
    path="/ask",
    input_type=LangServeRequest,
)

# Add LangServe routes for ANALYST mode
add_routes(
    app,
    langserve_stream_wrapper,
    path="/analyst", 
    input_type=LangServeRequest,
)

# Add legacy compatibility endpoint that matches the frontend expectation
@app.post("/chat/stream")
async def legacy_chat_stream(req: ChatRequest):
    """
    Legacy compatibility endpoint that redirects to LangServe streaming
    This ensures the frontend doesn't need to change
    """
    from fastapi.responses import StreamingResponse
    
    try:
        # Convert ChatRequest to LangServeRequest
        langserve_req = LangServeRequest(
            mode=req.mode,
            message=req.message,
            wid=req.wid,
            sid=req.sid,
            contexts=req.contexts,
            model=req.model
        )
        
        async def sse_generator():
            """Convert LangServe stream to SSE format"""
            request_id = f"sse-compat-{int(time.time()*1000)}"
            
            # Send start event
            start_event = f"event: start\ndata: {json.dumps({'type': 'start'})}\n\n"
            yield start_event
            
            # Stream content from LangServe
            async for chunk in langserve_stream_wrapper(langserve_req):
                if chunk.strip():  # Only send non-empty chunks
                    chunk_data = {"type": "chunk", "text": chunk}
                    sse_payload = f"event: chunk\ndata: {json.dumps(chunk_data)}\n\n"
                    yield sse_payload
                    await asyncio.sleep(0)  # Allow immediate flush
            
            # Send completion event
            complete_event = {"type": "complete", "sheet": None}
            sse_payload = f"event: complete\ndata: {json.dumps(complete_event)}\n\n"
            yield sse_payload
        
        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        print(f"Legacy chat stream error: {str(e)}")
        async def error_generator():
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream"
        )

# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0", "service": "langserve"}

# Root endpoint
@app.get("/")
async def root():
    return {"status": "cf0.ai LangServe API is running", "version": "2.0.0"}

# Add other essential endpoints from main.py for compatibility
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

# Essential compatibility endpoints for full frontend support
@app.get("/workbook/{wid}/sheets")
async def get_workbook_sheets(wid: str):
    """Get all sheets in a workbook"""
    wb = get_workbook(wid)
    return {
        "sheets": wb.list_sheets(),
        "active": wb.active
    }

# Update a specific sheet endpoint for frontend compatibility
class SheetUpdateRequest(BaseModel):
    cell: str  # e.g., "A1" or "Sheet2!A1"  
    value: Any  # Value to set

@app.post("/workbook/{wid}/sheet/{sid}/update")
async def update_sheet(request: SheetUpdateRequest, wid: str, sid: str):
    """Update a specific cell in a sheet"""
    try:
        from spreadsheet_engine.operations import set_cell
        
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

# Model catalog endpoints for frontend
@app.get("/models")
async def available_models():
    """Return a list of all available language models with their capabilities"""
    try:
        from llm.catalog import get_models
        return get_models()
    except ImportError:
        # Fallback if catalog not available
        return {"models": ["anthropic:claude-3-sonnet", "openai:gpt-4", "groq:llama-3-70b"]}

# Blocking chat endpoint for compatibility
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Blocking version of chat endpoint for compatibility"""
    import time
    import traceback
    
    start_time = time.time()
    request_id = f"chat-block-{int(time.time()*1000)}"
    print(f"[{request_id}] 📝 Blocking chat request: mode={req.mode}, wid={req.wid}, sid={req.sid}")
    
    try:
        # Get the workbook and active sheet
        wb = get_workbook(req.wid)
        if not wb:
            raise HTTPException(404, f"Workbook not found: {req.wid}")
        
        sheet = wb.sheet(req.sid)
        if not sheet:
            raise HTTPException(404, f"Sheet not found: {req.sid}")
        
        # Convert to LangServeRequest and collect all content
        langserve_req = LangServeRequest(
            mode=req.mode,
            message=req.message,
            wid=req.wid,
            sid=req.sid,
            contexts=req.contexts,
            model=req.model
        )
        
        # Collect all streaming content
        content_parts = []
        async for chunk in langserve_stream_wrapper(langserve_req):
            content_parts.append(chunk)
        
        content = "".join(content_parts)
        
        # Return in expected format
        return ChatResponse(
            reply=content,
            sheet=sheet.to_dict(),
            updates=[],  # Updates are applied during streaming
            all_sheets={name: s.to_dict() for name, s in wb.all_sheets().items()}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[{request_id}] ❌ Error in blocking chat: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 