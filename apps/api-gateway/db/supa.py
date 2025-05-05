import os
import json
import asyncio
from typing import Dict, Any, Optional, List
import traceback
from supabase import create_client, Client
from spreadsheet_engine.model import Spreadsheet

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dbvpltqumpfkdpsyqbvz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Create a client instance when the module is loaded
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Background queue for pending writes (to avoid blocking API responses)
_write_queue = asyncio.Queue()
_is_worker_running = False

async def _background_writer():
    """Background task to process database writes without blocking API responses."""
    global _is_worker_running
    
    try:
        _is_worker_running = True
        print("🔄 Background writer task started")
        
        while True:
            try:
                # Get next item from the queue with a timeout
                item = await asyncio.wait_for(_write_queue.get(), timeout=5.0)
                
                # Process the write operation
                operation, args = item
                
                if operation == "save_workbook":
                    workbook, sheets = args
                    await _do_save_workbook(workbook, sheets)
                
                elif operation == "save_sheet":
                    wid, sheet = args
                    await _do_save_sheet(wid, sheet)
                
                # Mark task as done
                _write_queue.task_done()
            
            except asyncio.TimeoutError:
                # No items in queue, but keep running
                continue
            except Exception as e:
                print(f"❌ Error in background writer: {str(e)}")
                traceback.print_exc()
                # Don't exit the loop on error
    
    except asyncio.CancelledError:
        print("⏹️ Background writer task cancelled")
    finally:
        _is_worker_running = False
        print("⏹️ Background writer task stopped")

def start_background_worker():
    """Start the background task for database writes if not already running."""
    global _is_worker_running
    
    if not _is_worker_running:
        asyncio.create_task(_background_writer())

async def _do_save_workbook(workbook_data: Dict[str, Any], sheets: List[Spreadsheet]) -> None:
    """
    Actually save a workbook and all its sheets to the database.
    This is called by the background worker.
    """
    try:
        wid = workbook_data["id"]
        
        # First, ensure the workbook exists
        workbook_response = supabase.table("workbooks").upsert({
            "wid": wid,
        }).execute()
        
        # Get the workbook UUID
        workbook_id = None
        if workbook_response.data:
            workbook_id = workbook_response.data[0]["id"]
        else:
            # Fetch the workbook ID if upsert didn't return it
            get_response = supabase.table("workbooks").select("id").eq("wid", wid).execute()
            if get_response.data:
                workbook_id = get_response.data[0]["id"]
        
        if not workbook_id:
            print(f"❌ Could not get workbook ID for {wid}")
            return
        
        # Now save each sheet
        for sheet in sheets:
            sheet_data = {
                "workbook_id": workbook_id,
                "workbook_wid": wid,
                "name": sheet.name,
                "n_rows": sheet.n_rows,
                "n_cols": sheet.n_cols,
                "cells": json.dumps(sheet.cells)
            }
            
            supabase.table("sheets").upsert(
                sheet_data,
                on_conflict=["workbook_wid", "name"]
            ).execute()
        
        print(f"✅ Saved workbook {wid} with {len(sheets)} sheets")
    
    except Exception as e:
        print(f"❌ Error saving workbook: {str(e)}")
        traceback.print_exc()

async def _do_save_sheet(wid: str, sheet: Spreadsheet) -> None:
    """
    Actually save a sheet to the database.
    This is called by the background worker.
    """
    try:
        # First, get the workbook ID
        workbook_response = supabase.table("workbooks").select("id").eq("wid", wid).execute()
        
        workbook_id = None
        if workbook_response.data:
            workbook_id = workbook_response.data[0]["id"]
        else:
            # Create the workbook if it doesn't exist
            create_response = supabase.table("workbooks").insert({"wid": wid}).execute()
            if create_response.data:
                workbook_id = create_response.data[0]["id"]
        
        if not workbook_id:
            print(f"❌ Could not get or create workbook ID for {wid}")
            return
        
        # Save the sheet
        sheet_data = {
            "workbook_id": workbook_id,
            "workbook_wid": wid,
            "name": sheet.name,
            "n_rows": sheet.n_rows,
            "n_cols": sheet.n_cols,
            "cells": json.dumps(sheet.cells)
        }
        
        supabase.table("sheets").upsert(
            sheet_data,
            on_conflict=["workbook_wid", "name"]
        ).execute()
        
        print(f"✅ Saved sheet {sheet.name} in workbook {wid}")
    
    except Exception as e:
        print(f"❌ Error saving sheet: {str(e)}")
        traceback.print_exc()

def save_workbook(workbook: Any) -> None:
    """
    Queue a workbook for background saving.
    
    Args:
        workbook: The workbook object to save
    """
    from workbook_store import Workbook
    
    if not isinstance(workbook, Workbook):
        print(f"❌ Invalid workbook type: {type(workbook)}")
        return
    
    # Extract basic workbook data
    workbook_data = {"id": workbook.id}
    
    # Get all sheets in the workbook
    sheets = list(workbook.sheets.values())
    
    # Queue this for background processing
    asyncio.create_task(_write_queue.put(("save_workbook", (workbook_data, sheets))))
    start_background_worker()

def save_sheet(wid: str, sheet: Spreadsheet) -> None:
    """
    Queue a single sheet for background saving.
    
    Args:
        wid: Workbook ID
        sheet: The sheet to save
    """
    # Queue this for background processing
    asyncio.create_task(_write_queue.put(("save_sheet", (wid, sheet))))
    start_background_worker()

async def load_workbook(wid: str) -> Dict[str, Dict]:
    """
    Load all sheets for a workbook from the database.
    
    Args:
        wid: Workbook ID
        
    Returns:
        Dict mapping sheet names to their data
    """
    try:
        # Check if the workbook exists
        response = supabase.table("sheets").select("*").eq("workbook_wid", wid).execute()
        
        if not response.data:
            print(f"⚠️ No sheets found for workbook {wid}")
            return {}
        
        # Build a dict of sheet data
        sheets = {}
        for sheet_data in response.data:
            sheet_name = sheet_data["name"]
            
            # Parse cell data from JSON if it's stored as a string
            cells = sheet_data["cells"]
            if isinstance(cells, str):
                cells = json.loads(cells)
            
            # Create sheet dict
            sheets[sheet_name] = {
                "name": sheet_name,
                "n_rows": sheet_data["n_rows"],
                "n_cols": sheet_data["n_cols"],
                "cells": cells
            }
        
        print(f"✅ Loaded {len(sheets)} sheets for workbook {wid}")
        return sheets
    
    except Exception as e:
        print(f"❌ Error loading workbook: {str(e)}")
        traceback.print_exc()
        return {} 