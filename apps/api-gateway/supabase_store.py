import os
import asyncio
import json
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from supabase import create_client, Client
from spreadsheet_engine.model import Spreadsheet

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from workbook_store import Workbook

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")

# Try all allowed key names – first one wins
supabase_key = (
    os.getenv("SUPABASE_KEY") or
    os.getenv("SUPABASE_SERVICE_ROLE_KEY") or
    os.getenv("SUPABASE_ANON_KEY")
)

if not supabase_url or not supabase_key:
    print("⚠️  Supabase persistence disabled – SUPABASE_URL / *_KEY env vars missing")
    sb: Optional[Client] = None
else:
    sb: Client = create_client(supabase_url, supabase_key)
    print("✅ Supabase client initialised")

# Queue for background persistence operations
save_queue = asyncio.Queue()

async def save_sheet_worker():
    """Background worker to process sheet save operations"""
    while True:
        try:
            wid, sheet = await save_queue.get()
            await _save_sheet(wid, sheet)
            save_queue.task_done()
        except Exception as e:
            print(f"Error in save_sheet_worker: {str(e)}")


async def _save_sheet(wid: str, sheet: Spreadsheet):
    """Save a sheet to Supabase (internal implementation)"""
    if not sb:
        print("Supabase client not initialized - skipping persistence")
        return
    
    try:
        # Prepare the data for Supabase
        data = {
            "workbook_wid": wid,
            "name": sheet.name,
            "n_rows": sheet.n_rows,
            "n_cols": sheet.n_cols,
            "cells": json.dumps(sheet.cells, default=str)
        }
        
        # Check if workbook exists, create it if it doesn't
        try:
            workbook_query = sb.table("spreadsheet_workbooks").select("wid").eq("wid", wid)
            workbook_data = workbook_query.execute()
            
            if len(workbook_data.data) == 0:
                # Create the workbook first
                workbook_insert = sb.table("spreadsheet_workbooks").insert({"wid": wid}).execute()
                print(f"Created workbook {wid} in Supabase")
        except Exception as workbook_error:
            # Enhanced RLS error handling for workbooks
            error_msg = str(workbook_error).lower()
            if "rls" in error_msg or "policy" in error_msg or "permission" in error_msg:
                print(f"🚨 RLS Policy Violation (workbook): User lacks permission to create/access workbook {wid}")
                print(f"🔍 RLS Error Details: {str(workbook_error)}")
                # Fallback: continue without workbook creation (sheet might still work)
            else:
                print(f"❌ Workbook creation error: {str(workbook_error)}")
                raise  # Re-raise non-RLS errors
        
        # Upsert the sheet with enhanced RLS error handling
        try:
            sheet_result = sb.table("spreadsheet_sheets").upsert(
                data, 
                on_conflict=["workbook_wid", "name"]
            ).execute()
            print(f"Saved sheet {sheet.name} for workbook {wid} to Supabase")
        except Exception as sheet_error:
            # Enhanced RLS error handling for sheets
            error_msg = str(sheet_error).lower()
            if "rls" in error_msg or "policy" in error_msg or "permission" in error_msg:
                print(f"🚨 RLS Policy Violation (sheet): User lacks permission to save sheet {sheet.name} in workbook {wid}")
                print(f"🔍 RLS Error Details: {str(sheet_error)}")
                print(f"💡 Fallback: Sheet changes will remain in memory only")
                # Continue execution - don't crash the application
                return
            else:
                print(f"❌ Sheet save error (non-RLS): {str(sheet_error)}")
                raise  # Re-raise non-RLS errors
        
    except Exception as e:
        # Catch-all error handling with RLS detection
        error_msg = str(e).lower()
        if "rls" in error_msg or "policy" in error_msg or "permission" in error_msg:
            print(f"🚨 RLS Policy Violation (general): {str(e)}")
            print(f"💡 Workbook persistence failed due to RLS policies - check user permissions")
        else:
            print(f"❌ General error saving sheet to Supabase: {str(e)}")
        # Don't re-raise to prevent application crashes


def save_sheet(wid: str, sheet: Spreadsheet):
    """
    Queue a sheet to be saved to Supabase asynchronously.
    
    Args:
        wid: Workbook ID
        sheet: The spreadsheet to save
    """
    if not sb:
        # Skip if Supabase is not configured
        return
    
    # Add to the background save queue
    try:
        save_queue.put_nowait((wid, sheet))
    except Exception as e:
        print(f"Error queuing sheet save: {str(e)}")


async def load_workbook(wid: str) -> Optional[Dict[str, Any]]:
    """
    Load a workbook and all its sheets from Supabase.
    
    Args:
        wid: Workbook ID
        
    Returns:
        Dictionary mapping sheet names to sheet data, or None if not found
    """
    if not sb:
        return None
    
    try:
        # Query for the workbook
        workbook_query = sb.table("spreadsheet_workbooks").select("*").eq("wid", wid)
        workbook_data = workbook_query.execute()
        
        if len(workbook_data.data) == 0:
            return None
        
        # Query for all sheets in this workbook
        sheets_query = sb.table("spreadsheet_sheets").select("*").eq("workbook_wid", wid)
        sheets_data = sheets_query.execute()
        
        if len(sheets_data.data) == 0:
            return None
        
        # Convert to the expected format
        result = {}
        for sheet_data in sheets_data.data:
            name = sheet_data["name"]
            cells = json.loads(sheet_data["cells"]) if isinstance(sheet_data["cells"], str) else sheet_data["cells"]
            
            result[name] = {
                "name": name,
                "rows": sheet_data["n_rows"],
                "columns": sheet_data["n_cols"],
                "cells": cells
            }
        
        return result
    except Exception as e:
        print(f"Error loading workbook from Supabase: {str(e)}")
        return None


# Start the background worker
async def start_background_worker():
    """Start the background worker for sheet persistence"""
    asyncio.create_task(save_sheet_worker()) 