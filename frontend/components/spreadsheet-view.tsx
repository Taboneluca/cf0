"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import type { SpreadsheetData } from "@/types/spreadsheet"
import { isFormula, evaluateFormula, detectCircularReferences } from "@/utils/formula-engine"
import { useWorkbook } from "@/context/workbook-context"
import { useEditing, makeA1 } from "@/context/editing-context"

interface SpreadsheetViewProps {
  data: SpreadsheetData
  onCellUpdate: (row: number, col: string, value: string) => void
  readOnly?: boolean
}

export default function SpreadsheetView({ data, onCellUpdate, readOnly = false }: SpreadsheetViewProps) {
  const [wb, dispatch] = useWorkbook()
  const { active, data: allSheets, selected } = wb
  const { 
    editingState, 
    startEdit, 
    updateDraft, 
    appendReference, 
    commitEdit, 
    cancelEdit 
  } = useEditing()

  const inputRef = useRef<HTMLInputElement>(null)
  const tableRef = useRef<HTMLTableElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const cellRefs = useRef<{ [key: string]: HTMLTableCellElement | null }>({})

  // Function to get cell coordinates from cell ID (e.g., "A1" -> {col: "A", row: 1})
  const getCellCoords = (cellId: string) => {
    const match = cellId.match(/^([A-Za-z]+)(\d+)$/)
    if (!match) return { col: "", row: 0 }
    const col = match[1]
    const row = Number.parseInt(match[2])
    return { col, row }
  }

  // Function to get cell ID from coordinates (e.g., {col: "A", row: 1} -> "A1")
  const getCellId = (col: string, row: number) => {
    return `${col}${row}`
  }

  // Function to get the raw value of a cell, supports cross-sheet references
  const getCellRawValue = (cellId: string, sheet = active): string => {
    const sheetData = allSheets[sheet]
    return sheetData?.cells[cellId]?.value ?? ""
  }

  // Function to get the displayed value of a cell (evaluates formulas)
  const getCellDisplayValue = (cellId: string): string => {
    const rawValue = getCellRawValue(cellId)

    if (isFormula(rawValue)) {
      return evaluateFormula(rawValue, getCellRawValue, active, allSheets)
    }

    return rawValue
  }

  // Function to select a cell without entering edit mode
  const selectCell = (col: string, row: number) => {
    const cellId = getCellId(col, row)
    dispatch({ type: "SELECT_CELL", cell: cellId })

    // Scroll cell into view immediately
    const cell = cellRefs.current[cellId]
    if (cell) {
      cell.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "auto" })
    }
  }

  // Check if a cell is currently being edited
  const isEditingCell = (cellId: string): boolean => {
    if (!editingState.isEditing) return false;
    
    const isOriginCell = (
      editingState.originSheet === active &&
      editingState.originCol === getCellCoords(cellId).col &&
      editingState.originRow === getCellCoords(cellId).row
    );
    
    return isOriginCell;
  }

  // Function to enter edit mode for a cell
  const editCell = (cellId: string, initialValue?: string, cursorToEnd = true) => {
    if (readOnly) return // Don't allow editing in read-only mode
    
    const { col, row } = getCellCoords(cellId);
    const cellValue = initialValue !== undefined ? initialValue : getCellRawValue(cellId);
    
    startEdit(active, row, col, cellValue);
    
    // Focus and position cursor appropriately after render
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus()
        if (cursorToEnd) {
          // Position cursor at the end
          const length = inputRef.current.value.length
          inputRef.current.setSelectionRange(length, length)
        } else {
          // Select all text
          inputRef.current.select()
        }
      }
    }, 0)
  }

  // Move selection by direction
  const moveSelectionBy = (direction: "up" | "down" | "left" | "right") => {
    if (selected) {
      const { col, row } = getCellCoords(selected)
      const colIndex = data.columns.indexOf(col)

      let newCol = col
      let newRow = row

      switch (direction) {
        case "up":
          if (row > 1) {
            newRow = row - 1
          }
          break
        case "down":
          if (row < data.rows.length) {
            newRow = row + 1
          }
          break
        case "left":
          if (colIndex > 0) {
            newCol = data.columns[colIndex - 1]
          }
          break
        case "right":
          if (colIndex < data.columns.length - 1) {
            newCol = data.columns[colIndex + 1]
          }
          break
      }

      selectCell(newCol, newRow)
      return { col: newCol, row: newRow };
    }
    return null;
  }

  // Move selection to specific coordinates
  const moveSelectionTo = (row: number, col: string) => {
    selectCell(col, row);
    return { col, row };
  }

  // Handle single click - select cell and insert reference if in formula mode
  const handleCellClick = (cellId: string) => {
    const { col, row } = getCellCoords(cellId);
    
    // If editing a formula, insert a reference to the clicked cell
    if (editingState.isEditing && editingState.draft.startsWith("=")) {
      const ref = makeA1(row, col, active, editingState.originSheet);
      appendReference(ref);
      selectCell(col, row);
      return;
    }
    
    // Otherwise just select the cell
    selectCell(col, row);
  }

  // Handle double click - enter edit mode
  const handleCellDoubleClick = (cellId: string) => {
    if (readOnly) return; // Don't allow editing in read-only mode
    
    // Enter edit mode for this cell
    editCell(cellId);
  }

  // Commit the current edit
  const handleCommitEdit = async () => {
    if (editingState.isEditing && editingState.originSheet && editingState.originRow && editingState.originCol) {
      const row = editingState.originRow;
      const col = editingState.originCol;
      
      // Check for circular references if it's a formula
      if (isFormula(editingState.draft)) {
        const cellId = getCellId(col, row);
        if (detectCircularReferences(cellId, editingState.draft, getCellRawValue)) {
          // Handle circular reference error
          alert("Circular reference detected. Formula not applied.");
          return;
        }
      }
      
      // Update the cell value
      onCellUpdate(row, col, editingState.draft);
      
      // Exit editing mode
      commitEdit();
    }
  }

  // Handle keyboard input when editing a cell
  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (!editingState.isEditing) return;
    
    // Handle special keys for formula navigation
    if (editingState.draft.startsWith("=") && 
       ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
      
      e.preventDefault(); // Don't move cursor in input
      
      // Move selection according to arrow key
      const direction = e.key.replace("Arrow", "").toLowerCase() as "up" | "down" | "left" | "right";
      const newPos = moveSelectionBy(direction);
      
      // Insert reference at cursor position if we successfully moved
      if (newPos) {
        // If this is the first navigation after typing "=", add the reference
        // Otherwise, just update the UI highlight without modifying the formula
        if (editingState.draft === "=") {
          const ref = makeA1(newPos.row, newPos.col, active, editingState.originSheet);
          appendReference(ref);
        }

        // Re-focus the input so the toolbar doesn't grab the focus
        setTimeout(() => {
          if (inputRef.current) {
            inputRef.current.focus();
            // Position cursor at the end
            inputRef.current.setSelectionRange(editingState.caretPos, editingState.caretPos);
          }
        }, 0);
      }
      
      return;
    }
    
    // Excel-like special handling for F4 key to cycle through reference types (A1, $A1, A$1, $A$1)
    if (e.key === "F4" && editingState.draft.startsWith("=")) {
      e.preventDefault();
      // This would require a more complex implementation to cycle through reference types
      // by modifying the formula - a future enhancement
      return;
    }
    
    // Handle F2 toggle between navigation and editing mode
    if (e.key === "F2") {
      e.preventDefault();
      // In Excel, F2 toggles between navigating with arrow keys and moving cursor in formula
      // This would require a mode flag - a future enhancement
      return;
    }
    
    // Handle other editing keys
    switch (e.key) {
      case "Enter":
        if (!e.shiftKey) {
          e.preventDefault();
          handleCommitEdit();
          
          // Move down if not holding Ctrl
          if (!e.ctrlKey) {
            moveSelectionBy("down");
          }
        }
        break;
        
      case "Tab":
        e.preventDefault();
        handleCommitEdit();
        
        // Move left or right
        if (e.shiftKey) {
          moveSelectionBy("left");
        } else {
          moveSelectionBy("right");
        }
        break;
        
      case "Escape":
        e.preventDefault();
        cancelEdit();
        break;
    }
  }

  // Handle input change when editing
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    updateDraft(newValue, e.target.selectionStart || 0);
  }

  // Handle cursor position changes
  const handleInputSelect = (e: React.SyntheticEvent<HTMLInputElement>) => {
    const input = e.target as HTMLInputElement;
    updateDraft(editingState.draft, input.selectionStart || 0);
  }

  // Handle key press when cell is selected but not in edit mode
  const handleSelectionKeyDown = (e: React.KeyboardEvent) => {
    if (!selected || editingState.isEditing) return;

    switch (e.key) {
      case "ArrowUp":
      case "ArrowDown":
      case "ArrowLeft":
      case "ArrowRight":
        e.preventDefault();
        moveSelectionBy(e.key.replace("Arrow", "").toLowerCase() as any);
        break;
        
      case "=":
        // Start formula edit mode
        if (!readOnly) {
          e.preventDefault();
          const { col, row } = getCellCoords(selected);
          startEdit(active, row, col, "=");
        }
        break;
        
      case "Enter":
        if (readOnly) {
          // In read-only mode, just navigate
          if (e.shiftKey) {
            moveSelectionBy("up");
          } else {
            moveSelectionBy("down");
          }
        } else {
          // In edit mode, enter edit mode
          e.preventDefault();
          editCell(selected);
        }
        break;
        
      case "Tab":
        e.preventDefault();
        if (e.shiftKey) {
          moveSelectionBy("left");
        } else {
          moveSelectionBy("right");
        }
        break;
        
      case "Home":
        e.preventDefault();
        if (e.ctrlKey) {
          // Ctrl+Home goes to A1
          selectCell("A", 1);
        } else {
          // Home goes to first cell in row
          const { row } = getCellCoords(selected);
          selectCell(data.columns[0], row);
        }
        break;
        
      case "End":
        e.preventDefault();
        if (e.ctrlKey) {
          // Ctrl+End goes to last cell
          selectCell(data.columns[data.columns.length - 1], data.rows[data.rows.length - 1]);
        } else {
          // End goes to last cell in row
          const { row } = getCellCoords(selected);
          selectCell(data.columns[data.columns.length - 1], row);
        }
        break;
        
      case "Delete":
      case "Backspace":
        if (!readOnly) {
          // Clear cell content
          e.preventDefault();
          const { col, row } = getCellCoords(selected);
          onCellUpdate(row, col, "");
        }
        break;
        
      case "F2":
        // Excel-like F2 to enter edit mode without clearing cell
        if (!readOnly) {
          e.preventDefault();
          editCell(selected, undefined, true);
        }
        break;
        
      default:
        // If user starts typing a printable character, enter edit mode with that character
        if (!readOnly && e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
          e.preventDefault();
          const { col, row } = getCellCoords(selected);
          startEdit(active, row, col, e.key);
          
          // Ensure focus stays in the cell
          setTimeout(() => {
            if (inputRef.current) {
              inputRef.current.focus();
            }
          }, 0);
        }
        break;
    }
  }

  // Handle keyboard events at the container level
  const handleContainerKeyDown = (e: React.KeyboardEvent) => {
    // Don't handle keyboard events for toolbar navigation
    if (e.target !== containerRef.current && !(e.target as Element)?.closest?.("table")) {
      return;
    }

    if (editingState.isEditing) {
      // Let the editing input handle its own keyboard events
      return;
    }

    if (selected) {
      // Handle navigation when a cell is selected
      handleSelectionKeyDown(e);
    } else if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Tab", "Home", "End"].includes(e.key)) {
      // If no cell is selected, select A1 on any navigation key
      e.preventDefault();
      selectCell("A", 1);
    }
  }

  // Cell ref callback function that follows React requirements
  const setCellRef = (cellId: string, element: HTMLTableCellElement | null) => {
    cellRefs.current[cellId] = element;
  };

  // Auto-focus the cell input when editing starts
  useEffect(() => {
    if (editingState.isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [editingState.isEditing]);

  return (
    <div
      className="spreadsheet-container overflow-auto h-full outline-none"
      tabIndex={0}
      onKeyDown={handleContainerKeyDown}
      ref={containerRef}
    >
      <div className="min-w-max">
        <table className="border-collapse" ref={tableRef}>
          <thead>
            <tr>
              <th className="w-6 h-6 bg-gray-50 border-b border-r border-gray-200 sticky top-0 left-0 z-20"></th>
              {data.columns.map((col) => (
                <th
                  key={col}
                  className="min-w-[80px] w-[1%] h-6 bg-gray-50 border-b border-r border-gray-200 text-xs font-medium text-gray-600 sticky top-0 z-10"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row}>
                <td className="w-6 h-6 bg-gray-50 border-r border-b border-gray-200 text-xs font-medium text-gray-600 text-center sticky left-0 z-10">
                  {row}
                </td>
                {data.columns.map((col) => {
                  const cellId = `${col}${row}`
                  const isSelected = selected === cellId
                  const currentlyEditing = isEditingCell(cellId)
                  const rawValue = getCellRawValue(cellId)
                  const displayValue = getCellDisplayValue(cellId)
                  const isFormulaCell = isFormula(rawValue)
                  const isReferenced = editingState.isEditing && 
                                      editingState.draft.startsWith('=') && 
                                      selected === cellId &&
                                      !currentlyEditing;

                  return (
                    <td
                      id={`cell-${cellId}`}
                      key={cellId}
                      ref={(el) => setCellRef(cellId, el)}
                      className={`min-w-[80px] w-[1%] h-6 border-r border-b border-gray-200 relative ${
                        isSelected ? "bg-blue-50" : ""
                      } ${isFormulaCell ? "text-green-700" : ""} ${
                        isReferenced ? "outline outline-2 outline-blue-300" : ""
                      } ${
                        readOnly ? "cursor-default" : "cursor-cell"
                      } hover:bg-blue-50 transition-colors`}
                      onClick={() => handleCellClick(cellId)}
                      onDoubleClick={() => handleCellDoubleClick(cellId)}
                      tabIndex={-1}
                    >
                      {currentlyEditing ? (
                        <input
                          ref={inputRef}
                          type="text"
                          value={editingState.draft}
                          onChange={handleInputChange}
                          onKeyDown={handleEditKeyDown}
                          onSelect={handleInputSelect}
                          className="w-full h-full border-none focus:ring-0 focus:outline-none text-xs p-0"
                          autoFocus
                        />
                      ) : (
                        <div className="w-full h-full overflow-hidden text-xs p-1">{displayValue}</div>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
