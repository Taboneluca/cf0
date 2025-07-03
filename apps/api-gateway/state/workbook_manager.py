"""
Thread-safe workbook manager with proper async/await handling.
"""
import asyncio
import time
from typing import Dict, Optional
from contextlib import asynccontextmanager

from ..spreadsheet_engine.model import Spreadsheet
from ..workbook_store import Workbook
from .. import supabase_store


class WorkbookManager:
    """Thread-safe workbook manager with LRU eviction."""
    
    def __init__(self, max_workbooks: int = 1000):
        self._workbooks: Dict[str, Workbook] = {}
        self._lock = asyncio.Lock()
        self._max_workbooks = max_workbooks
        self._access_times: Dict[str, float] = {}
        self._loading_tasks: Dict[str, asyncio.Task] = {}
    
    async def get_workbook(self, wid: str) -> Workbook:
        """
        Get a workbook by ID, loading from database if necessary.
        
        Args:
            wid: Workbook ID
            
        Returns:
            Workbook instance
        """
        async with self._lock:
            # Check if already loaded
            if wid in self._workbooks:
                self._access_times[wid] = time.time()
                return self._workbooks[wid]
            
            # Check if currently loading
            if wid in self._loading_tasks:
                # Release lock and wait for loading to complete
                loading_task = self._loading_tasks[wid]
                
        # Wait outside the lock to avoid blocking other operations
        if 'loading_task' in locals():
            try:
                await loading_task
                # Re-acquire lock and return the loaded workbook
                async with self._lock:
                    return self._workbooks.get(wid)
            except Exception:
                # Loading failed, will try again below
                pass
        
        # Load the workbook
        async with self._lock:
            # Double-check after re-acquiring lock
            if wid in self._workbooks:
                return self._workbooks[wid]
            
            # LRU eviction if needed
            if len(self._workbooks) >= self._max_workbooks:
                await self._evict_lru()
            
            # Create loading task
            self._loading_tasks[wid] = asyncio.create_task(
                self._load_or_create(wid)
            )
        
        # Wait for loading to complete
        try:
            workbook = await self._loading_tasks[wid]
            
            async with self._lock:
                self._workbooks[wid] = workbook
                self._access_times[wid] = time.time()
                del self._loading_tasks[wid]
                return workbook
                
        except Exception as e:
            async with self._lock:
                if wid in self._loading_tasks:
                    del self._loading_tasks[wid]
            raise e
    
    async def get_sheet(self, wid: str, sid: str) -> Spreadsheet:
        """
        Get a specific sheet from a workbook.
        
        Args:
            wid: Workbook ID
            sid: Sheet ID
            
        Returns:
            Spreadsheet instance
        """
        workbook = await self.get_workbook(wid)
        sheet = workbook.sheet(sid)
        
        # Schedule save
        asyncio.create_task(self._save_sheet(wid, sheet))
        
        return sheet
    
    async def delete_workbook(self, wid: str) -> None:
        """Delete a workbook from memory."""
        async with self._lock:
            self._workbooks.pop(wid, None)
            self._access_times.pop(wid, None)
            
            # Cancel any loading task
            if wid in self._loading_tasks:
                self._loading_tasks[wid].cancel()
                del self._loading_tasks[wid]
    
    async def _load_or_create(self, wid: str) -> Workbook:
        """Load workbook from database or create new one."""
        try:
            # Try to load from Supabase
            sheet_data = await supabase_store.load_workbook(wid)
            
            if sheet_data:
                # Create workbook from loaded data
                workbook = Workbook(wid)
                
                # Fill in sheets from database
                for sheet_name, data in sheet_data.items():
                    if sheet_name == "Sheet1" and sheet_name in workbook.sheets:
                        # Update existing Sheet1
                        sheet = workbook.sheets[sheet_name]
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
                        workbook.sheets[sheet_name] = sheet
                        sheet.workbook = workbook
                
                return workbook
                
        except Exception as e:
            print(f"Error loading workbook from database: {e}")
        
        # Create new workbook
        workbook = Workbook(wid)
        
        # Schedule save for new workbook
        asyncio.create_task(self._save_workbook(workbook))
        
        return workbook
    
    async def _evict_lru(self) -> None:
        """Evict least recently used workbook."""
        if not self._access_times:
            return
            
        oldest_wid = min(self._access_times.items(), key=lambda x: x[1])[0]
        
        # Save before evicting
        if oldest_wid in self._workbooks:
            await self._save_workbook(self._workbooks[oldest_wid])
        
        # Remove from cache
        del self._workbooks[oldest_wid]
        del self._access_times[oldest_wid]
    
    async def _save_workbook(self, workbook: Workbook) -> None:
        """Save workbook to database."""
        try:
            await supabase_store.save_workbook(workbook)
        except Exception as e:
            print(f"Error saving workbook: {e}")
    
    async def _save_sheet(self, wid: str, sheet: Spreadsheet) -> None:
        """Save sheet to database."""
        try:
            await supabase_store.save_sheet(wid, sheet)
        except Exception as e:
            print(f"Error saving sheet: {e}")
    
    @asynccontextmanager
    async def transaction(self, wid: str):
        """
        Context manager for transactional workbook operations.
        
        Usage:
            async with manager.transaction(wid) as workbook:
                # Make changes to workbook
                workbook.new_sheet("Sheet2")
        """
        workbook = await self.get_workbook(wid)
        try:
            yield workbook
            # Save on successful completion
            await self._save_workbook(workbook)
        except Exception:
            # Could implement rollback here if needed
            raise


# Global instance
_manager: Optional[WorkbookManager] = None


def get_manager() -> WorkbookManager:
    """Get the global WorkbookManager instance."""
    global _manager
    if _manager is None:
        _manager = WorkbookManager()
    return _manager


# Backwards compatibility functions
async def get_workbook_async(wid: str) -> Workbook:
    """Async version of get_workbook for backwards compatibility."""
    manager = get_manager()
    return await manager.get_workbook(wid)


async def get_sheet_async(wid: str, sid: str) -> Spreadsheet:
    """Async version of get_sheet for backwards compatibility."""
    manager = get_manager()
    return await manager.get_sheet(wid, sid)


def get_workbook_sync(wid: str) -> Workbook:
    """
    Synchronous wrapper for get_workbook.
    WARNING: This can cause issues if called from an async context.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context - this is problematic
            # Create a temporary in-memory workbook as fallback
            print(f"WARNING: Synchronous get_workbook called from async context for {wid}")
            from ..workbook_store import workbooks
            if wid not in workbooks:
                workbooks[wid] = Workbook(wid)
            return workbooks[wid]
        else:
            # Safe to run synchronously
            return loop.run_until_complete(get_workbook_async(wid))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(get_workbook_async(wid))


def get_sheet_sync(wid: str, sid: str) -> Spreadsheet:
    """
    Synchronous wrapper for get_sheet.
    WARNING: This can cause issues if called from an async context.
    """
    workbook = get_workbook_sync(wid)
    return workbook.sheet(sid) 