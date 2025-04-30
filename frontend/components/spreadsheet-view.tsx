"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import type { SpreadsheetData } from "@/types/spreadsheet"
import { isFormula, evaluateFormula, detectCircularReferences } from "@/utils/formula-engine"
import { useWorkbook } from "@/context/workbook-context"
import SheetTabs from "./sheet-tabs"

interface SpreadsheetViewProps {
  data: SpreadsheetData
  onCellUpdate: (row: number, col: string, value: string) => void
  readOnly?: boolean
}

interface EditingState {
  formulaMode: boolean;
  buffer: string;
  originalValue: string;
  cursorPosition: number;
  anchor: number;       // Position where the current reference starts
}

export default function SpreadsheetView({ data, onCellUpdate, readOnly = false }: SpreadsheetViewProps) {
  const [selectedCell, setSelectedCell] = useState<string | null>(null)
  const [editingCell, setEditingCell] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const [editingState, setEditingState] = useState<EditingState>({
    formulaMode: false,
    buffer: "",
    originalValue: "",
    cursorPosition: 0,
    anchor: 0
  })
  const inputRef = useRef<HTMLInputElement>(null)
  const tableRef = useRef<HTMLTableElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const cellRefs = useRef<{ [key: string]: HTMLTableCellElement | null }>({})
  const [wb, dispatch] = useWorkbook()
  const { wid, active } = wb

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

  // Function to get the raw value of a cell
  const getCellRawValue = (cellId: string): string => {
    return data.cells[cellId]?.value || ""
  }

  // Function to get the displayed value of a cell (evaluates formulas)
  const getCellDisplayValue = (cellId: string): string => {
    const rawValue = getCellRawValue(cellId)

    if (isFormula(rawValue)) {
      return evaluateFormula(rawValue, getCellRawValue)
    }

    return rawValue
  }

  // Function to select a cell without entering edit mode
  const selectCell = (col: string, row: number) => {
    const cellId = getCellId(col, row)
    setSelectedCell(cellId)

    // Scroll cell into view immediately
    const cell = cellRefs.current[cellId]
    if (cell) {
      cell.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "auto" })
    }
  }

  // Function to enter edit mode for a cell
  const editCell = (cellId: string, initialValue?: string, cursorToEnd = true) => {
    if (readOnly) return // Don't allow editing in read-only mode

    setEditingCell(cellId)
    // When editing, show the raw formula, not the evaluated result
    const cellValue = initialValue !== undefined ? initialValue : getCellRawValue(cellId)
    setEditValue(cellValue)
    
    // Reset formula mode state
    setEditingState({
      formulaMode: false,
      buffer: cellValue,
      originalValue: cellValue,
      cursorPosition: cursorToEnd ? cellValue.length : 0,
      anchor: 0
    })

    // Check if this is a formula and set formula mode
    if (cellValue && cellValue.startsWith('=')) {
      setEditingState({
        formulaMode: true,
        buffer: cellValue,
        originalValue: cellValue,
        cursorPosition: cellValue.length,
        anchor: 1 // Right after the = sign
      })
    }

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

  // Insert cell reference at current cursor position
  const insertCellReference = (col: string, row: number) => {
    if (!inputRef.current || !editingState.formulaMode) return
    
    const cellRef = getCellId(col, row)
    const { buffer, anchor } = editingState
    
    // Replace any existing reference after anchor point with the new reference
    const newValue = 
      buffer.substring(0, anchor) + 
      cellRef
    
    // Update the buffer and cursor position
    setEditValue(newValue)
    setEditingState({
      ...editingState,
      buffer: newValue,
      cursorPosition: anchor + cellRef.length,
      anchor: anchor  // Keep same anchor point for potential further navigation
    })
    
    // Set cursor position after reference
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus()
        inputRef.current.setSelectionRange(
          anchor + cellRef.length,
          anchor + cellRef.length
        )
      }
    }, 0)
  }

  // Handle single click - just select the cell
  const handleCellClick = (cellId: string) => {
    // If already editing, commit changes first
    if (editingCell) {
      commitEdit()
    }

    setSelectedCell(cellId)
  }

  // Handle double click - enter edit mode
  const handleCellDoubleClick = (cellId: string) => {
    if (readOnly) return // Don't allow editing in read-only mode

    setSelectedCell(cellId)
    editCell(cellId, undefined, true) // Position cursor at end on double-click (Excel behavior)
  }

  // Commit the current edit
  const commitEdit = async () => {
    if (editingCell) {
      const { col, row } = getCellCoords(editingCell)

      // Check for circular references if it's a formula
      if (isFormula(editValue)) {
        if (detectCircularReferences(editingCell, editValue, getCellRawValue)) {
          // Handle circular reference error
          alert("Circular reference detected. Formula not applied.")
          return
        }
      }

      // Update the UI state
      onCellUpdate(row, col, editValue)
      
      // Send update to backend
      try {
        if (wid) {
          await fetch(
            `${process.env.NEXT_PUBLIC_BACKEND_URL}/workbook/${wid}/sheet/${active}/update`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ cell: editingCell, value: editValue })
            }
          );
        }
      } catch (error) {
        console.error("Error updating cell on backend:", error)
      }
      
      // Exit formula mode and editing mode
      setEditingState({
        formulaMode: false,
        buffer: "",
        originalValue: "",
        cursorPosition: 0,
        anchor: 0
      })
      setEditingCell(null)
    }
  }

  // Handle keyboard navigation
  const navigateSelection = (direction: "up" | "down" | "left" | "right") => {
    if (selectedCell) {
      const { col, row } = getCellCoords(selectedCell)
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

      // If in formula mode, insert the cell reference
      if (editingState.formulaMode && editingCell) {
        insertCellReference(newCol, newRow)
      }
      
      // Always select the new cell to give visual feedback
      selectCell(newCol, newRow)
    }
  }

  // Update cursor position when input value changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    setEditValue(newValue)
    
    if (editingState.formulaMode) {
      setEditingState({
        ...editingState,
        buffer: newValue,
        cursorPosition: e.target.selectionStart || 0
      })
    }
  }

  // Track cursor position as user navigates within input
  const handleInputSelect = (e: React.SyntheticEvent<HTMLInputElement>) => {
    if (editingState.formulaMode) {
      const input = e.target as HTMLInputElement
      setEditingState({
        ...editingState,
        cursorPosition: input.selectionStart || 0
      })
    }
  }

  // Handle key press when editing a cell
  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (!editingCell) return

    // If the user types "=" at the beginning of the input, enter formula mode
    if (e.key === "=" && !editingState.formulaMode && 
        (editValue === "" || inputRef.current?.selectionStart === 0)) {
      setEditingState({
        formulaMode: true,
        buffer: "=",
        originalValue: editValue,
        cursorPosition: 1,
        anchor: 1  // Set anchor right after the = sign
      })
      setEditValue("=")
      e.preventDefault()
      return
    }

    // If in formula mode and user presses an arrow key, navigate and insert cell reference
    if (editingState.formulaMode && ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
      const direction = e.key.replace("Arrow", "").toLowerCase() as "up" | "down" | "left" | "right"
      navigateSelection(direction)
      e.preventDefault()
      return
    }

    // Handle formula mode operators
    if (editingState.formulaMode && ["+", "-", "*", "/", "^", "(", ")"].includes(e.key)) {
      const { buffer, cursorPosition } = editingState
      const newValue = 
        buffer.substring(0, cursorPosition) + 
        e.key + 
        buffer.substring(cursorPosition)
      
      setEditValue(newValue)
      const newCursorPos = cursorPosition + 1
      setEditingState({
        ...editingState,
        buffer: newValue,
        cursorPosition: newCursorPos,
        anchor: newCursorPos  // Set anchor after the operator for next cell reference
      })
      
      // Set cursor position after the operator
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus()
          inputRef.current.setSelectionRange(
            newCursorPos,
            newCursorPos
          )
        }
      }, 0)
      
      e.preventDefault()
      return
    }

    // Add navigation across sheets with Ctrl+PgUp/PgDn
    if (e.ctrlKey && (e.key === "PageUp" || e.key === "PageDown")) {
      const currentIndex = wb.sheets.indexOf(active);
      if (currentIndex >= 0) {
        const direction = e.key === "PageUp" ? -1 : 1;
        const nextIndex = (currentIndex + direction + wb.sheets.length) % wb.sheets.length;
        const nextSheet = wb.sheets[nextIndex];
        if (nextSheet && editingState.formulaMode) {
          // Only switch sheet during formula editing
          dispatch({ type: "SWITCH", sid: nextSheet });
          e.preventDefault();
          return;
        }
      }
    }

    switch (e.key) {
      case "Enter":
        commitEdit()
        if (e.shiftKey) {
          navigateSelection("up")
        } else {
          navigateSelection("down")
        }
        e.preventDefault()
        break
      case "Tab":
        commitEdit()
        if (e.shiftKey) {
          navigateSelection("left")
        } else {
          navigateSelection("right")
        }
        e.preventDefault()
        break
      case "Escape":
        // Cancel edit and revert to original value
        setEditingCell(null)
        setEditingState({
          formulaMode: false,
          buffer: "",
          originalValue: "",
          cursorPosition: 0,
          anchor: 0
        })
        e.preventDefault()
        break
    }
  }

  // Handle key press when a cell is selected but not in edit mode
  const handleSelectionKeyDown = (e: React.KeyboardEvent) => {
    if (!selectedCell || editingCell) return

    switch (e.key) {
      case "ArrowUp":
        navigateSelection("up")
        e.preventDefault()
        break
      case "ArrowDown":
        navigateSelection("down")
        e.preventDefault()
        break
      case "ArrowLeft":
        navigateSelection("left")
        e.preventDefault()
        break
      case "ArrowRight":
        navigateSelection("right")
        e.preventDefault()
        break
      case "Enter":
        if (readOnly) {
          // In read-only mode, just navigate
          if (e.shiftKey) {
            navigateSelection("up")
          } else {
            navigateSelection("down")
          }
        } else {
          // In edit mode, enter edit mode
          editCell(selectedCell)
        }
        e.preventDefault()
        break
      case "Tab":
        if (e.shiftKey) {
          // Shift+Tab moves left in selection mode
          navigateSelection("left")
        } else {
          // Tab moves right in selection mode
          navigateSelection("right")
        }
        e.preventDefault()
        break
      case "F2":
        if (!readOnly) {
          // F2 enters edit mode with cursor at the end (Excel behavior)
          editCell(selectedCell, undefined, true)
        }
        e.preventDefault()
        break
      case "=":
        if (!readOnly) {
          // Starting with = enters formula mode
          editCell(selectedCell, "=", true)
          setEditingState({
            formulaMode: true,
            buffer: "=",
            originalValue: "",
            cursorPosition: 1,
            anchor: 1  // Set anchor right after the = for formula mode
          })
          e.preventDefault()
        }
        break
      case "Home":
        if (e.ctrlKey) {
          // Ctrl+Home goes to A1 (Excel behavior)
          selectCell("A", 1)
        } else {
          // Home goes to first cell in row (Excel behavior)
          const { row } = getCellCoords(selectedCell)
          selectCell(data.columns[0], row)
        }
        e.preventDefault()
        break
      case "End":
        if (e.ctrlKey) {
          // Ctrl+End goes to last cell with data (simplified here)
          selectCell(data.columns[data.columns.length - 1], data.rows[data.rows.length - 1])
        } else {
          // End goes to last cell in row (Excel behavior)
          const { row } = getCellCoords(selectedCell)
          selectCell(data.columns[data.columns.length - 1], row)
        }
        e.preventDefault()
        break
      case "Delete":
      case "Backspace":
        if (!readOnly) {
          // Clear cell content (Excel behavior)
          const { col, row } = getCellCoords(selectedCell)
          onCellUpdate(row, col, "")
        }
        e.preventDefault()
        break
      default:
        // If user starts typing, enter edit mode and set the first character
        if (!readOnly && e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
          editCell(selectedCell, e.key, true)
          e.preventDefault()
        }
        break
    }
  }

  // Handle keyboard events at the container level
  const handleContainerKeyDown = (e: React.KeyboardEvent) => {
    // Don't handle keyboard events for toolbar navigation
    if (e.target !== containerRef.current && !(e.target as Element)?.closest?.("table")) {
      return
    }

    if (editingCell) {
      // Let the editing input handle its own keyboard events
      return
    }

    if (selectedCell) {
      // Handle navigation when a cell is selected
      handleSelectionKeyDown(e)
    } else {
      // If no cell is selected, select A1 on any navigation key
      switch (e.key) {
        case "ArrowUp":
        case "ArrowDown":
        case "ArrowLeft":
        case "ArrowRight":
        case "Enter":
        case "Tab":
        case "Home":
        case "End":
          selectCell("A", 1)
          e.preventDefault()
          break
      }
    }
  }

  // Cell ref callback function that follows React requirements
  const setCellRef = (cellId: string, element: HTMLTableCellElement | null) => {
    cellRefs.current[cellId] = element;
  };

  useEffect(() => {
    if (editingCell && inputRef.current) {
      inputRef.current.focus()
    }
  }, [editingCell])

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
                  const isSelected = selectedCell === cellId
                  const isEditing = editingCell === cellId
                  const rawValue = getCellRawValue(cellId)
                  const displayValue = getCellDisplayValue(cellId)
                  const isFormulaCell = isFormula(rawValue)
                  const isReferenced = editingState.formulaMode && selectedCell && selectedCell !== cellId && 
                                       editValue.includes(cellId);

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
                      {isEditing ? (
                        <input
                          ref={inputRef}
                          type="text"
                          value={editValue}
                          onChange={handleInputChange}
                          onSelect={handleInputSelect}
                          onBlur={commitEdit}
                          onKeyDown={handleEditKeyDown}
                          className={`w-full h-full p-1 outline-none border border-blue-400 absolute top-0 left-0 z-30 ${
                            editingState.formulaMode ? "bg-yellow-50" : ""
                          }`}
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
