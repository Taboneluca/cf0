from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import os
import asyncio
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from spreadsheet_engine import (
    Spreadsheet, 
    set_cell, 
    create_new_sheet,
    summarize_sheet,
    DEFAULT_ROWS,
    DEFAULT_COLS
)
from workbook_store import get_sheet, get_workbook, workbooks, initialize as initialize_workbook_store
from chat.router import process_message
from agents.openai_client import client, OpenAIError
from chat.memory import clear_history
import json
from fastapi.responses import StreamingResponse
from spreadsheet_engine.adapter import get_implementation_info
from spreadsheet_engine.adapter import SpreadsheetAdapter
import time

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
class ChatRequest(BaseModel):
    mode: str
    message: str
    wid: str
    sid: str

class ChatResponse(BaseModel):
    reply: str
    sheet: Dict[str, Any]
    log: List[Dict[str, Any]]

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
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    import time
    import traceback
    
    start_time = time.time()
    request_id = f"req-{int(time.time()*1000)}"
    print(f"[{request_id}] 📝 Chat request received: mode={req.mode}, wid={req.wid}, sid={req.sid}")
    
    try:
        # Try to use moderation if available, but don't fail if it doesn't work
        try:
            moderation = client.moderations.create(input=req.message)
            if moderation.results[0].flagged:
                print(f"[{request_id}] ⚠️ Message flagged by moderation")
                raise HTTPException(400, "Message violates policy")
        except OpenAIError as moderation_error:
            # Log the error but continue processing the message
            print(f"[{request_id}] ⚠️ Moderation check failed: {moderation_error}")
        
        # Get the workbook and active sheet
        print(f"[{request_id}] 🔍 Getting workbook {req.wid} and sheet {req.sid}")
        try:
            wb = get_workbook(req.wid)
            if not wb:
                print(f"[{request_id}] ❌ Workbook not found: {req.wid}")
                raise HTTPException(404, f"Workbook not found: {req.wid}")
            
            sheet = wb.sheet(req.sid)
            if not sheet:
                print(f"[{request_id}] ❌ Sheet not found: {req.sid} in workbook {req.wid}")
                print(f"[{request_id}] 📋 Available sheets: {wb.list_sheets()}")
                raise HTTPException(404, f"Sheet not found: {req.sid}")
            
            print(f"[{request_id}] ✅ Found workbook with {len(wb.list_sheets())} sheets")
        except Exception as e:
            print(f"[{request_id}] ❌ Error getting workbook/sheet: {str(e)}")
            traceback.print_exc()
            raise HTTPException(500, f"Error accessing workbook or sheet: {str(e)}")
        
        # Create metadata with all sheets in the workbook for cross-sheet formulas
        all_sheets_data = {
            name: sheet.to_dict() for name, sheet in wb.all_sheets().items()
        }
        
        print(f"[{request_id}] 🕒 Preparing to process message with {len(wb.list_sheets())} available sheets")
        
        # Process the message with the sheet and workbook context - rate limited
        async with chat_limiter:
            print(f"[{request_id}] 🚀 Processing message through agent (mode: {req.mode})")
            process_start = time.time()
            
            try:
                result = await process_message(
                    req.mode, 
                    req.message, 
                    req.wid, 
                    req.sid, 
                    sheet,
                    workbook_metadata={
                        "sheets": wb.list_sheets(),
                        "active": req.sid,
                        "all_sheets_data": all_sheets_data
                    }
                )
                process_time = time.time() - process_start
                print(f"[{request_id}] ⏱️ Message processed in {process_time:.2f}s")
            except Exception as process_error:
                print(f"[{request_id}] ❌ Error in process_message: {str(process_error)}")
                traceback.print_exc()
                raise HTTPException(500, f"Error processing message: {str(process_error)}")
        
        # Verify the result structure before returning
        if not isinstance(result, dict) or "reply" not in result or "sheet" not in result:
            print(f"[{request_id}] ❌ Invalid result structure: {result.keys() if isinstance(result, dict) else type(result)}")
            raise HTTPException(500, "Invalid response format from agent")
        
        total_time = time.time() - start_time
        print(f"[{request_id}] ✅ Request completed in {total_time:.2f}s with reply length: {len(result['reply'])}")
        
        return ChatResponse(**result)
    except HTTPException:
        # Re-raise HTTP exceptions without modifying them
        raise
    except Exception as e:
        print(f"[{request_id}] ❌ Unhandled error processing chat request: {str(e)}")
        tb = traceback.format_exc()
        print(f"[{request_id}] 📋 Traceback: {tb}")
        
        # For debugging purposes, try to identify if this is a sheet access error
        if "Sheet is None" in str(e):
            print(f"[{request_id}] 🔍 Sheet access error detected for wid={req.wid}, sid={req.sid}")
            try:
                wb = get_workbook(req.wid)
                sheet_list = wb.list_sheets() if wb else []
                print(f"[{request_id}] 📋 Available sheets: {sheet_list}")
            except Exception as inner_e:
                print(f"[{request_id}] ❌ Failed to get sheet list: {str(inner_e)}")
        
        total_time = time.time() - start_time
        print(f"[{request_id}] ❌ Request failed after {total_time:.2f}s")
        raise HTTPException(status_code=500, detail=str(e))

# Chat endpoint with streaming support
@app.post("/chat/stream")
async def stream_chat(req: ChatRequest):
    """
    Streaming version of the chat endpoint that uses Server-Sent Events (SSE)
    to deliver partial responses as they are generated.
    """
    try:
        # Try to use moderation if available
        try:
            moderation = client.moderations.create(input=req.message)
            if moderation.results[0].flagged:
                raise HTTPException(400, "Message violates policy")
        except OpenAIError as moderation_error:
            # Log the error but continue processing the message
            print(f"Warning: Moderation check failed: {moderation_error}")
        
        # Get the workbook and active sheet
        wb = get_workbook(req.wid)
        sheet = wb.sheet(req.sid)
        
        # Create metadata with all sheets
        all_sheets_data = {
            name: sheet.to_dict() for name, sheet in wb.all_sheets().items()
        }
        
        # Define the streaming generator
        async def event_generator():
            # First, send a "start" event
            yield f"event: start\ndata: {json.dumps({'status': 'processing'})}\n\n"
            
            # Process the message with streaming
            async for chunk in process_message_streaming(
                req.mode, 
                req.message, 
                req.wid, 
                req.sid, 
                sheet,
                workbook_metadata={
                    "sheets": wb.list_sheets(),
                    "active": req.sid,
                    "all_sheets_data": all_sheets_data
                }
            ):
                # Send each chunk as a "chunk" event
                yield f"event: chunk\ndata: {json.dumps(chunk)}\n\n"
            
            # Add a final state event
            final_sheet = sheet.optimized_to_dict(max_rows=30, max_cols=30)
            final_state = {
                "event": "complete",
                "sheet": final_sheet,
                "all_sheets": {name: s.optimized_to_dict(max_rows=30, max_cols=30) for name, s in wb.all_sheets().items()},
            }
            yield f"event: complete\ndata: {json.dumps(final_state)}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        print(f"Error processing streaming chat request: {str(e)}")
        # Return an error event
        async def error_generator():
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream"
        )

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
        "spreadsheet_engine": get_implementation_info(),
        "environment": {
            "USE_DATAFRAME_MODEL": os.getenv("USE_DATAFRAME_MODEL", "0"),
            "USE_FORMULA_ENGINE": os.getenv("USE_FORMULA_ENGINE", "0"),
            "USE_INCREMENTAL_RECALC": os.getenv("USE_INCREMENTAL_RECALC", "1"),
            "MAX_TOOL_ITERATIONS": os.getenv("MAX_TOOL_ITERATIONS", "10"),
            "MODEL": os.getenv("OPENAI_MODEL", "gpt-4o")
        },
        "versions": {
            "pandas": __import__("pandas").__version__,
            "numpy": __import__("numpy").__version__
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 