from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
import os
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from spreadsheet_engine import (
    Spreadsheet, 
    set_cell, 
    create_new_sheet,
    summarize_sheet,
    get_workbook,
    get_sheet,
    DEFAULT_ROWS,
    DEFAULT_COLS
)
from workbook_store import get_sheet, get_workbook, workbooks
from chat.router import process_message
from agents.openai_client import client, OpenAIError
from chat.memory import clear_history

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
    try:
        # Try to use moderation if available, but don't fail if it doesn't work
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
        
        # Create metadata with all sheets in the workbook for cross-sheet formulas
        all_sheets_data = {
            name: sheet.to_dict() for name, sheet in wb.all_sheets().items()
        }
        
        # Process the message with the sheet and workbook context
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
        
        return ChatResponse(**result)
    except Exception as e:
        print(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 