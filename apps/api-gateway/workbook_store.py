from __future__ import annotations
from typing import Dict, Set, List, Any, Optional
from collections import defaultdict, deque
import asyncio
import os

from spreadsheet_engine.model import Spreadsheet   # SAFE direction
import supabase_store  # Import the Supabase persistence layer
from spreadsheet_engine.dag_recalc import get_recalculation_order, clear_dirty_cells

# Whether to use optimized incremental recalculation
USE_INCREMENTAL_RECALC = os.getenv("USE_INCREMENTAL_RECALC", "1").lower() in ("1", "true", "yes")

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
        
        # Trigger persistence
        self._schedule_save()
        
        return self.sheets[name]

    def list_sheets(self) -> list[str]:
        # Filter out hidden sheets (those starting with underscore)
        return [name for name in self.sheets.keys() if not name.startswith("_")]
        
    def all_sheets(self) -> Dict[str, Spreadsheet]:
        """Get all sheets in the workbook"""
        return self.sheets
        
    def recalculate(self) -> None:
        """
        Recalculate formula cells in the workbook. 
        Uses fast incremental recalculation if enabled, or full recalc otherwise.
        
        Note: This is a synchronous wrapper around the async version for backwards compatibility.
        """
        import asyncio
        try:
            if asyncio.get_event_loop().is_running():
                # We're in an async context, create a task 
                asyncio.create_task(self.recalculate_async())
            else:
                # We're not in an async context, run synchronously
                if USE_INCREMENTAL_RECALC:
                    self._incremental_recalculate()
                else:
                    self._full_recalculate()
        except Exception as e:
            print(f"Error in recalculate: {e}")
            # Fallback to synchronous execution
            if USE_INCREMENTAL_RECALC:
                self._incremental_recalculate()
            else:
                self._full_recalculate()
                
    async def recalculate_async(self) -> None:
        """
        Asynchronous version of recalculate.
        Allows non-blocking recalculation when called with asyncio.create_task.
        """
        if USE_INCREMENTAL_RECALC:
            self._incremental_recalculate()
        else:
            self._full_recalculate()
                
    def _incremental_recalculate(self) -> None:
        """
        Perform incremental recalculation using the DAG-based engine.
        Only recalculates cells that need to be updated.
        """
        # Get the optimal recalculation order
        recalc_order = get_recalculation_order()
        
        # If no cells need recalculation, we're done
        if not recalc_order:
            return
            
        print(f"Incrementally recalculating {len(recalc_order)} cells")
        
        # Process cells in the proper order
        for cell_ref in recalc_order:
            # Handle cross-sheet references
            if '!' in cell_ref:
                sheet_name, local_cell = cell_ref.split('!', 1)
                try:
                    sheet = self.sheet(sheet_name)
                    # Just accessing the cell will recalculate if it's a formula
                    sheet.get_cell(local_cell)
                except Exception as e:
                    print(f"Error recalculating {cell_ref}: {e}")
            else:
                # Should not happen with qualified cell refs
                print(f"Warning: unqualified cell reference {cell_ref} in recalculation order")
        
        # Clear dirty cells after recalculation
        clear_dirty_cells()
    
    def _full_recalculate(self) -> None:
        """
        Legacy full recalculation method.
        Recalculates all formula cells in all sheets using topological sort.
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
                
    def _schedule_save(self):
        """Schedule this workbook to be saved to the database."""
        try:
            from db import save_workbook
            save_workbook(self)
        except ImportError:
            # DB module not available, skip
            pass
        except Exception as e:
            print(f"Error scheduling workbook save: {e}")


# GLOBAL REGISTRY  ------------------------------------------
workbooks: Dict[str, Workbook] = {}

# Flag to indicate if we should attempt to load from database
_try_load_from_db = True

def get_workbook(wid: str) -> Workbook:
    global _try_load_from_db
    
    if wid not in workbooks:
        # Check if we can load from the database
        if _try_load_from_db:
            try:
                from db import load_workbook
                import asyncio
                
                # Try to load the workbook from the database
                # Check if we're already in an async context
                if asyncio.get_event_loop().is_running():
                    # We are in an async context, use create_task
                    try:
                        # Start the DB fetch in the background; we *do not* block
                        # inside this synchronous function.
                        sheet_data_future = asyncio.create_task(load_workbook(wid))
                        sheet_data = {}                 # continue with empty workbook
                    except Exception as e:
                        print(f"Error loading workbook in async context: {e}")
                        sheet_data = {}
                else:
                    # Not in async context, safe to use asyncio.run
                    sheet_data = asyncio.run(load_workbook(wid))
                
                if sheet_data:
                    # Workbook exists in the database, create it
                    workbooks[wid] = Workbook(wid)
                    
                    # Fill in sheets from database
                    for sheet_name, data in sheet_data.items():
                        if sheet_name == "Sheet1" and sheet_name in workbooks[wid].sheets:
                            # Update existing Sheet1
                            sheet = workbooks[wid].sheets[sheet_name]
                            sheet.n_rows = data["n_rows"]
                            sheet.n_cols = data["n_cols"]
                            sheet.cells = data["cells"]
                        else:
                            # Create new sheet
                            sheet = Spreadsheet(
                                rows=data["n_rows"],
                                cols=data["n_cols"],
                                name=sheet_name
                            )
                            sheet.cells = data["cells"]
                            workbooks[wid].sheets[sheet_name] = sheet
                            sheet.workbook = workbooks[wid]
                    
                    # Don't schedule save since we just loaded
                    return workbooks[wid]
            
            except ImportError:
                # DB module not available, skipping load attempt
                _try_load_from_db = False
            except Exception as e:
                print(f"Error loading workbook from database: {e}")
        
        # No database data or error loading, create a new workbook
        workbooks[wid] = Workbook(wid)
        
        # Schedule save for new workbook
        workbooks[wid]._schedule_save()
    
    return workbooks[wid]

def get_sheet(wid: str, sid: str) -> Spreadsheet:
    sheet = get_workbook(wid).sheet(sid)
    
    # Schedule save whenever a sheet is accessed
    try:
        from db import save_sheet
        save_sheet(wid, sheet)
    except ImportError:
        # DB module not available, skip
        pass
    except Exception as e:
        print(f"Error scheduling sheet save: {e}")
    
    return sheet


# Module initialization
async def initialize():
    """Initialize the workbook store and start background workers"""
    await supabase_store.start_background_worker() 