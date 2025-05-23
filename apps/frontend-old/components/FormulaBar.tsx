"use client"

import React, { useRef, useEffect } from "react"
import { useWorkbook } from "@/context/workbook-context"
import { useEditing } from "@/context/editing-context"

interface FormulaBarProps {
  handleCellUpdate: (row: number, col: string, value: string, sheetId?: string) => void
}

export default function FormulaBar({ handleCellUpdate }: FormulaBarProps) {
  const [wb, dispatch] = useWorkbook()
  const { active, data, selected } = wb
  const { 
    editingState, 
    startEdit, 
    updateDraft, 
    commitEdit, 
    cancelEdit 
  } = useEditing()
  
  const inputRef = useRef<HTMLInputElement>(null)

  // Get cell coordinates from ID
  const getCellCoords = (cellId: string) => {
    const match = cellId.match(/^([A-Za-z]+)(\d+)$/)
    if (!match) return { col: "", row: 0 }
    return { col: match[1], row: Number.parseInt(match[2]) }
  }

  // Show either the formula being edited or the selected cell value
  const display = editingState.isEditing
    ? editingState.draft
    : selected && data[active]?.cells[selected]
      ? data[active].cells[selected].value
      : ""

  // Focus input when formula editing starts or when cell selection changes
  useEffect(() => {
    if (editingState.isEditing && inputRef.current) {
      inputRef.current.focus()
      // Position cursor at specified position or end of input
      const position = editingState.caretPos || editingState.draft.length
      inputRef.current.setSelectionRange(position, position)
    }
  }, [editingState.isEditing, editingState.draft, editingState.caretPos])
    
  // Update the formula bar when a new cell is selected (Excel-like behavior)
  useEffect(() => {
    if (!editingState.isEditing && selected && inputRef.current) {
      // Just update display, don't grab focus from the grid
      // This mimics Excel's behavior of showing the raw formula in the bar
      // but keeping focus in the grid for keyboard navigation
    }
  }, [selected, active, data])

  // Handle toolbar input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    
    // If we're not in editing mode but user starts typing in formula bar,
    // start editing the currently selected cell
    if (!editingState.isEditing && selected) {
      const { col, row } = getCellCoords(selected)
      startEdit(active, row, col, newValue)
      return
    }
    
    updateDraft(newValue, e.target.selectionStart || 0)
  }

  // Handle selection position changes
  const handleInputSelect = (e: React.SyntheticEvent<HTMLInputElement>) => {
    const input = e.target as HTMLInputElement
    updateDraft(editingState.draft, input.selectionStart || 0)
  }

  // Handle keyboard events
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!editingState.isEditing) {
      // If "=" is pressed when not in formula mode, start formula edit
      if (e.key === "=" && selected) {
        e.preventDefault()
        const { col, row } = getCellCoords(selected)
        startEdit(active, row, col, "=")
      }
      return
    }
    
    if (e.key === "Enter") {
      e.preventDefault()
      // Commit the formula
      if (editingState.originSheet && editingState.originRow && editingState.originCol) {
        handleCellUpdate(
          editingState.originRow, 
          editingState.originCol, 
          editingState.draft, 
          editingState.originSheet
        )
        commitEdit()
      }
    } else if (e.key === "Escape") {
      e.preventDefault()
      // Cancel the formula
      cancelEdit()
    }
  }

  // Start editing when clicking on the formula bar if a cell is selected
  const handleFormulaBarClick = () => {
    if (!editingState.isEditing && selected) {
      const { col, row } = getCellCoords(selected)
      const cellValue = data[active]?.cells[selected]?.value || ""
      startEdit(active, row, col, cellValue)
    }
  }

  return (
    <div className="w-full border-b border-gray-200 bg-white p-1">
      <div className="flex items-center">
        <div className="text-xs text-gray-500 mr-2">
          {selected || (editingState.isEditing ? `${editingState.originCol}${editingState.originRow}` : "")}
        </div>
        <input
          ref={inputRef}
          type="text"
          value={display}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onSelect={handleInputSelect}
          onClick={handleFormulaBarClick}
          className="flex-1 px-2 py-1 border border-gray-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
        />
      </div>
    </div>
  )
} 