"""
Dependency-aware Graph (DAG) recalculation module.

This module provides an optimized incremental recalculation engine
that only recomputes cells that depend on changed cells, using a
directed acyclic graph (DAG) to track dependencies.
"""

from typing import Dict, Set, List, Any, Tuple
from collections import defaultdict, deque

class RecalculationEngine:
    """
    Manages the dependency graph and performs incremental recalculation.
    """
    
    def __init__(self):
        # Graph that maps cell IDs to the cells that depend on them
        # {precedent_cell: set(dependent_cells)}
        self.forward_deps = defaultdict(set)
        
        # Reverse graph that maps cells to the cells they depend on
        # {dependent_cell: set(precedent_cells)}
        self.reverse_deps = defaultdict(set)
        
        # Cache that tracks which cells contain formulas
        self.formula_cells = set()
        
        # Set of cells that have been modified and need recalculation
        self.dirty_cells = set()
    
    def register_formula(self, target_cell: str, dependencies: Set[str]) -> None:
        """
        Register a formula cell and its dependencies in the graph.
        
        Args:
            target_cell: The cell containing the formula (e.g., 'A1' or 'Sheet1!A1')
            dependencies: Set of cells this formula depends on
        """
        target_cell = self._normalize_cell_ref(target_cell)
        
        # Add to formula cells
        self.formula_cells.add(target_cell)
        
        # Clear previous dependencies for this cell
        for prev_dep in self.reverse_deps.get(target_cell, set()):
            self.forward_deps[prev_dep].discard(target_cell)
        self.reverse_deps[target_cell] = set()
        
        # Register new dependencies
        for dep in dependencies:
            dep = self._normalize_cell_ref(dep)
            self.forward_deps[dep].add(target_cell)
            self.reverse_deps[target_cell].add(dep)
        
        # Mark this cell as needing recalculation
        self.dirty_cells.add(target_cell)
    
    def unregister_formula(self, cell_ref: str) -> None:
        """
        Remove a formula cell from the dependency graph.
        
        Args:
            cell_ref: The cell reference to remove
        """
        cell_ref = self._normalize_cell_ref(cell_ref)
        
        # Remove from formula cells
        self.formula_cells.discard(cell_ref)
        
        # Remove from dependency graph
        for dep in self.reverse_deps.get(cell_ref, set()):
            self.forward_deps[dep].discard(cell_ref)
        
        # Remove reverse deps
        if cell_ref in self.reverse_deps:
            del self.reverse_deps[cell_ref]
        
        # Also remove any forward dependencies where this cell is a precedent
        for dependent in list(self.forward_deps.get(cell_ref, set())):
            self.reverse_deps[dependent].discard(cell_ref)
        
        # Remove forward deps
        if cell_ref in self.forward_deps:
            del self.forward_deps[cell_ref]
    
    def mark_dirty(self, cell_ref: str) -> None:
        """
        Mark a cell as modified, requiring itself and dependents to be recalculated.
        
        Args:
            cell_ref: The cell reference that was modified
        """
        cell_ref = self._normalize_cell_ref(cell_ref)
        self.dirty_cells.add(cell_ref)
        
        # Mark all cells that depend on this one (directly or indirectly) as dirty
        self._mark_dependents_dirty(cell_ref)
    
    def _mark_dependents_dirty(self, cell_ref: str) -> None:
        """
        Recursively mark all cells that depend on this one as dirty.
        
        Args:
            cell_ref: The cell reference whose dependents should be marked dirty
        """
        visited = set()
        queue = deque([cell_ref])
        
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
                
            visited.add(current)
            
            # Mark direct dependents as dirty and add them to the queue
            for dependent in self.forward_deps.get(current, set()):
                self.dirty_cells.add(dependent)
                queue.append(dependent)
    
    def get_recalculation_order(self) -> List[str]:
        """
        Determine the optimal order for recalculating dirty cells using topological sort.
        
        Returns:
            List of cell references in the order they should be recalculated
        """
        # We only need to recalculate dirty formula cells
        dirty_formulas = self.dirty_cells.intersection(self.formula_cells)
        
        # Create a subgraph of the dependency graph that includes only dirty cells
        # and their precedents
        subgraph_deps = defaultdict(set)
        for cell in dirty_formulas:
            for precedent in self.reverse_deps.get(cell, set()):
                if precedent in self.formula_cells:
                    subgraph_deps[cell].add(precedent)
        
        # Perform topological sort on the subgraph
        recalc_order = []
        visited = set()
        temp_visited = set()  # For cycle detection
        
        def visit(cell):
            if cell in temp_visited:
                # Cycle detected
                return False
                
            if cell in visited:
                return True
                
            temp_visited.add(cell)
            
            # Visit dependencies first
            for precedent in subgraph_deps.get(cell, set()):
                if not visit(precedent):
                    return False
            
            temp_visited.remove(cell)
            visited.add(cell)
            recalc_order.append(cell)
            return True
        
        # Try to visit each dirty formula cell
        for cell in dirty_formulas:
            if cell not in visited:
                if not visit(cell):
                    # Cycle detected, use simpler approach
                    print(f"Dependency cycle detected, falling back to simpler recalculation")
                    return list(dirty_formulas)
        
        return recalc_order
    
    def clear_dirty_cells(self) -> None:
        """Clear the set of dirty cells after recalculation."""
        self.dirty_cells.clear()
    
    def clear_all(self) -> None:
        """Clear all dependency information."""
        self.forward_deps.clear()
        self.reverse_deps.clear()
        self.formula_cells.clear()
        self.dirty_cells.clear()
    
    def _normalize_cell_ref(self, cell_ref: str) -> str:
        """Normalize cell references to uppercase for consistent lookup."""
        if '!' in cell_ref:
            sheet, cell = cell_ref.split('!', 1)
            return f"{sheet.upper()}!{cell.upper()}"
        return cell_ref.upper()


# Module-level recalculation engine for global use
_global_engine = RecalculationEngine()

def register_formula(cell_ref: str, dependencies: Set[str]) -> None:
    """Register a formula in the global recalculation engine."""
    _global_engine.register_formula(cell_ref, dependencies)

def unregister_formula(cell_ref: str) -> None:
    """Unregister a formula from the global recalculation engine."""
    _global_engine.unregister_formula(cell_ref)

def mark_dirty(cell_ref: str) -> None:
    """Mark a cell as dirty in the global recalculation engine."""
    _global_engine.mark_dirty(cell_ref)

def get_recalculation_order() -> List[str]:
    """Get the optimal recalculation order from the global engine."""
    return _global_engine.get_recalculation_order()

def clear_dirty_cells() -> None:
    """Clear dirty cells in the global engine."""
    _global_engine.clear_dirty_cells()

def create_engine() -> RecalculationEngine:
    """Create a new recalculation engine instance."""
    return RecalculationEngine() 