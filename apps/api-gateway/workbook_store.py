from __future__ import annotations
from typing import Dict, Set, List, Any, Optional
from collections import defaultdict, deque
import asyncio

from spreadsheet_engine.model import Spreadsheet   # SAFE direction
import supabase_store  # Import the Supabase persistence layer

class Workbook:
    def __init__(self, wid: str):
        self.id = wid
        self.sheets: Dict[str, Spreadsheet] = {"Sheet1": Spreadsheet(name="Sheet1")}
        self.active = "Sheet1"
        
        # Set workbook reference in sheets
        for sheet in self.sheets.values():
            sheet.workbook = self

    # helpers -------------------------------------------------
    def sheet(self, sid: str | None = None) -> Spreadsheet:
        if sid is None:
            sid = self.active
        
        # Normalize sheet name to uppercase for case-insensitive comparison
        sid_upper = sid.upper()
        
        # Try to find the sheet with case-insensitive match
        for sheet_name, sheet in self.sheets.items():
            if sheet_name.upper() == sid_upper:
                return sheet
        
        # If sheet doesn't exist, create it instead of returning a dummy
        # (this fixes the cross-sheet reference error)
        self.sheets[sid] = Spreadsheet(name=sid)
        self.sheets[sid].workbook = self
        return self.sheets[sid]

    def new_sheet(self, name: str) -> Spreadsheet:
        # Check case-insensitive to avoid confusion with similar sheet names
        for existing_name in self.sheets.keys():
            if existing_name.upper() == name.upper():
                raise ValueError(f"Sheet with name similar to {name} already exists: {existing_name}")
                
        self.sheets[name] = Spreadsheet(name=name)
        self.sheets[name].workbook = self  # Set reference to workbook
        self.active = name
        
        # Persist the new sheet
        supabase_store.save_sheet(self.id, self.sheets[name])
        
        return self.sheets[name]

    def list_sheets(self) -> list[str]:
        return list(self.sheets.keys())
        
    def all_sheets(self) -> Dict[str, Spreadsheet]:
        """Get all sheets in the workbook"""
        return self.sheets
        
    def recalculate(self) -> None:
        """
        Recalculate all formula cells in all sheets of the workbook.
        Uses topological sort to compute in the correct order.
        """
        # Collect all dependencies from all sheets
        all_deps = defaultdict(set)
        
        # Map of cell -> (sheet, local_cell_ref)
        cell_map = {}
        
        # Collect dependencies from all sheets
        for sheet_name, sheet in self.sheets.items():
            # Collect each sheet's dependencies
            for target, precedents in sheet.deps.items():
                # For local refs, prefix with sheet name
                if "!" not in target:
                    qualified_target = f"{sheet_name.upper()}!{target}"
                else:
                    qualified_target = target
                    
                cell_map[qualified_target] = (sheet_name, target.split("!", 1)[1] if "!" in target else target)
                
                # Add dependencies
                for precedent in precedents:
                    if "!" not in precedent:
                        # Local reference, prefix with sheet name
                        qualified_precedent = f"{sheet_name.upper()}!{precedent}"
                    else:
                        qualified_precedent = precedent
                        
                    all_deps[qualified_target].add(qualified_precedent)
                    
                    # Make sure the precedent is in the cell map
                    if qualified_precedent not in cell_map:
                        prec_sheet, prec_cell = (
                            qualified_precedent.split("!", 1) if "!" in qualified_precedent 
                            else (sheet_name, qualified_precedent)
                        )
                        cell_map[qualified_precedent] = (prec_sheet, prec_cell)
        
        # Find cells with no dependencies (base values)
        no_deps = {cell for cell in cell_map if not all_deps[cell]}
        
        # Perform topological sort (Kahn's algorithm)
        recalc_order = []
        queue = deque(no_deps)
        
        while queue:
            # Get a cell with no dependencies
            current = queue.popleft()
            recalc_order.append(current)
            
            # Find cells that depend on this one
            dependents = [cell for cell in all_deps if current in all_deps[cell]]
            
            for dependent in dependents:
                # Remove this dependency
                all_deps[dependent].remove(current)
                
                # If all dependencies have been satisfied, add to queue
                if not all_deps[dependent]:
                    queue.append(dependent)
        
        # Anything left with dependencies is part of a cycle (or unreachable)
        # Mark them as circular references
        circular_refs = {cell for cell in all_deps if all_deps[cell]}
        
        # Process recalculation order
        for cell_ref in recalc_order:
            sheet_name, local_cell = cell_map[cell_ref]
            try:
                # Get the sheet and force recalculation of the cell
                sheet = self.sheet(sheet_name)
                if "!" in local_cell:
                    # This shouldn't happen, but handle it just in case
                    _, local_cell = local_cell.split("!", 1)
                
                if sheet and local_cell:
                    try:
                        # Just calling get_cell will recalculate if it's a formula
                        sheet.get_cell(local_cell)
                    except Exception as e:
                        print(f"Error recalculating {cell_ref}: {e}")
            except Exception as e:
                print(f"Error during recalculation: {e}")


# GLOBAL REGISTRY  ------------------------------------------
workbooks: Dict[str, Workbook] = {}

async def _load_from_supabase(wid: str) -> Optional[Workbook]:
    """Try to load a workbook from Supabase"""
    try:
        sheets_data = await supabase_store.load_workbook(wid)
        if not sheets_data:
            return None
            
        # Create workbook
        wb = Workbook(wid)
        
        # Clear default sheets
        wb.sheets.clear()
        
        # Add all sheets from Supabase
        for sheet_name, sheet_data in sheets_data.items():
            sheet = Spreadsheet.from_dict(sheet_data)
            sheet.workbook = wb
            wb.sheets[sheet_name] = sheet
            
        if wb.sheets:
            # Set active sheet to first one
            wb.active = next(iter(wb.sheets.keys()))
            
        return wb
    except Exception as e:
        print(f"Error loading workbook from Supabase: {str(e)}")
        return None

def get_workbook(wid: str) -> Workbook:
    """
    Get a workbook by ID, loading from persistence if needed.
    
    Args:
        wid: Workbook ID
        
    Returns:
        The workbook instance
    """
    if wid not in workbooks:
        # Try to load from Supabase asynchronously
        try:
            # Use an existing loop if one is running, or create a new one
            try:
                loop = asyncio.get_running_loop()
                # Create a future and run a task that will set the future's result
                future = asyncio.run_coroutine_threadsafe(_load_from_supabase(wid), loop)
                wb = future.result(timeout=10)  # Wait for up to 10 seconds
            except RuntimeError:
                # No running event loop, create a new one
                loop = asyncio.new_event_loop()
                wb = loop.run_until_complete(_load_from_supabase(wid))
                loop.close()
            
            if wb:
                workbooks[wid] = wb
            else:
                # Create a new workbook if not found in Supabase
                workbooks[wid] = Workbook(wid)
        except Exception as e:
            print(f"Error loading workbook: {str(e)}")
            # Fall back to creating a new in-memory workbook
            workbooks[wid] = Workbook(wid)
    
    return workbooks[wid]

def save_sheet_to_supabase(wid: str, sheet: Spreadsheet):
    """
    Save a sheet to persistent storage.
    
    This function is called directly from Spreadsheet.set_cell 
    to ensure changes are persisted.
    
    Args:
        wid: Workbook ID
        sheet: The spreadsheet to save
    """
    # Use the Supabase store for persistence
    supabase_store.save_sheet(wid, sheet)

def get_sheet(wid: str, sid: str) -> Spreadsheet:
    """
    Get a sheet from a workbook.
    
    Args:
        wid: Workbook ID
        sid: Sheet ID
        
    Returns:
        The spreadsheet instance
    """
    sheet = get_workbook(wid).sheet(sid)
    
    # After any get_sheet operation, schedule persistence
    supabase_store.save_sheet(wid, sheet)
    
    return sheet


# Module initialization
async def initialize():
    """Initialize the workbook store and start background workers"""
    await supabase_store.start_background_worker() 