"use client"

import React from "react"
import { Plus } from "lucide-react"
import { useWorkbook } from "@/context/workbook-context"
import { createSheet, fetchSheet } from "@/utils/backend"
import { backendSheetToUI } from "@/utils/transform"

export default function SheetTabs() {
  const [wb, dispatch] = useWorkbook()
  const { wid, sheets, active, formula } = wb

  // Handle tab click - different behavior during formula editing
  const clickTab = async (sid: string) => {
    if (sid === active) return
    
    // If the sheet data isn't loaded yet, fetch it
    if (!wb.data[sid]) {
      try {
        const sheetData = await fetchSheet(wid, sid)
        dispatch({
          type: "UPDATE_SHEET",
          sid,
          data: sheetData
        })
      } catch (error) {
        console.error("Error fetching sheet:", error)
      }
    }
    
    // Switch to the selected sheet
    dispatch({ type: "SWITCH", sid })
    
    // If in formula editing mode, we don't end the edit - user can continue building the formula
  }

  // Create a new sheet
  const handleAddSheet = async () => {
    try {
      const { sheets: newSheets, active: newActive, sheet } = await createSheet(wid)
      dispatch({
        type: "ADD_SHEET",
        sid: newActive,
        data: backendSheetToUI(sheet)
      })
    } catch (error) {
      console.error("Error creating sheet:", error)
    }
  }

  return (
    <div className="border-t border-gray-200 bg-white px-2 pt-1 flex items-center sheet-tabs">
      {sheets.map((sid) => (
        <button
          key={sid}
          onClick={() => clickTab(sid)}
          className={`px-3 py-1 mr-1 text-xs rounded-t-md ${
            active === sid 
              ? "bg-blue-50 border border-b-0 border-gray-200 font-medium" 
              : "bg-gray-50 hover:bg-gray-100"
          }`}
        >
          {sid}
        </button>
      ))}
      <button
        onClick={handleAddSheet}
        className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
      >
        <Plus size={16} />
      </button>
    </div>
  )
} 