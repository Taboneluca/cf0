"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import SpreadsheetView from "./spreadsheet-view"
import ChatInterface from "./chat-interface"
import type { SpreadsheetData, Message } from "@/types/spreadsheet"
import ToolbarRibbon from "./toolbar-ribbon"
import SheetTabs from "./sheet-tabs"
import FormulaBar from "./FormulaBar"
import { useWorkbook } from "@/context/workbook-context"
import { EditingProvider } from "@/context/editing-context"
import { Loader2 } from "lucide-react"
import { backendSheetToUIMap } from "@/utils/transform"

interface SpreadsheetInterfaceProps {
  initialData?: SpreadsheetData
  onDataChange?: (data: SpreadsheetData) => void
  readOnly?: boolean
}

export default function SpreadsheetInterface({
  initialData,
  onDataChange,
  readOnly = false,
}: SpreadsheetInterfaceProps) {
  const router = useRouter();
  // Get workbook state from context
  const [wb, dispatch, loading] = useWorkbook()
  const { wid, active, data } = wb
  const sheetData = data[active]

  // Fall back to SSR data so user sees a grid instantly
  useEffect(() => {
    if (initialData && Object.keys(data).length === 0) {
      dispatch({
        type: "INIT",
        wid,
        sheets: ["Sheet1"],
        active: "Sheet1",
        data: { "Sheet1": initialData }
      });
    }
  }, [initialData, wid]);

  const [mode, setMode] = useState<"ask" | "analyst">("ask")
  const [messages, setMessages] = useState<Message[]>([])

  // Initialize welcome message only once
  useEffect(() => {
    // Only set the welcome message if there are no messages
    if (messages.length === 0) {
      setMessages([{
        role: "system",
        content: "Welcome to the Spreadsheet Assistant. I can help you analyze your data or modify your spreadsheet based on your instructions.",
        id: "welcome_message"
      }])
    }
  }, [])

  // Enhanced updateCell that handles cross-sheet references
  const updateCell = async (row: number, col: string, value: string, sheetId?: string) => {
    if (readOnly) return

    const targetSheet = sheetId || active
    const cellId = `${col}${row}`
    
    // Don't update if value hasn't changed
    if (wb.data[targetSheet]?.cells[cellId]?.value === value) return
    
    dispatch({
      type: "UPDATE_SHEET", 
      sid: targetSheet,
      data: {
        ...wb.data[targetSheet], 
        cells: {
          ...wb.data[targetSheet].cells, 
          [cellId]: { value }
        }
      }
    })

    // Send to backend
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/workbook/${wid}/sheet/${targetSheet}/update`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cell: cellId, value })
        }
      );
      
      if (!response.ok) {
        throw new Error('Failed to update cell');
      }
      
      // Parse response and update state
      const result = await response.json();
      
      // If all_sheets data is included, merge it into the state
      if (result.all_sheets) {
        dispatch({
          type: "MERGE_SHEETS_DATA",
          data: backendSheetToUIMap(result.all_sheets)
        });
      }
    } catch (error) {
      console.error("Error updating cell on backend:", error)
    }
  }

  // Notify parent component of data changes
  useEffect(() => {
    if (sheetData) {
      onDataChange?.(sheetData)
    }
  }, [sheetData, onDataChange])

  // Add these new state variables and functions at the top of the component
  const [chatWidth, setChatWidth] = useState(300)
  const [isResizing, setIsResizing] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)

  // Update the startResizing and handleMouseMove functions to allow for a much smaller chat panel
  const startResizing = (e: React.MouseEvent) => {
    setIsResizing(true)
    document.addEventListener("mousemove", handleMouseMove)
    document.addEventListener("mouseup", stopResizing)
  }

  const handleMouseMove = (e: MouseEvent) => {
    if (isResizing) {
      const newWidth = window.innerWidth - e.clientX
      // Allow the chat to be much smaller, down to 40px minimum
      setChatWidth(Math.max(40, Math.min(newWidth, window.innerWidth * 0.7)))
    }
  }

  const stopResizing = () => {
    setIsResizing(false)
    document.removeEventListener("mousemove", handleMouseMove)
    document.removeEventListener("mouseup", stopResizing)
  }

  const toggleMinimize = () => {
    setIsMinimized(!isMinimized)
    if (isMinimized) {
      setChatWidth(300) // Reduced from 400px to 300px
    } else {
      setChatWidth(40)
    }
  }

  // Add useEffect to clean up event listeners
  useEffect(() => {
    return () => {
      document.removeEventListener("mousemove", handleMouseMove)
      document.removeEventListener("mouseup", stopResizing)
    }
  }, [isResizing])

  // Function to create a new workbook
  const createNewWorkbook = () => {
    const newId = crypto.randomUUID();
    router.push(`/workbook/${newId}`);
  };

  return (
    <EditingProvider>
      <div className="flex flex-col h-full w-full overflow-hidden bg-white">
        <div className="flex flex-1 overflow-hidden">
          {/* Spreadsheet section */}
          <div
            className="flex flex-col flex-1" 
            style={{ width: isMinimized ? "calc(100% - 40px)" : `calc(100% - ${chatWidth}px)` }}
          >
            <ToolbarRibbon />
            <FormulaBar handleCellUpdate={updateCell} />
            <div className="flex-1 min-h-0 overflow-auto">
              {loading ? (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                </div>
              ) : sheetData ? (
                <SpreadsheetView data={sheetData} onCellUpdate={updateCell} readOnly={readOnly} />
              ) : null}
            </div>
            <SheetTabs />
          </div>

          {/* Resize handle */}
          <div
            className="w-1 cursor-col-resize hover:bg-blue-400 active:bg-blue-500 transition-colors"
            onMouseDown={startResizing}
          />

          {/* Chat panel */}
          <div
            className="flex flex-col border-l border-gray-200 max-w-[40vw]"
            style={{ width: isMinimized ? "40px" : `${chatWidth}px`, flexShrink: 0 }}
          >
            <ChatInterface
              messages={messages}
              setMessages={setMessages}
              mode={mode}
              setMode={setMode}
              isMinimized={isMinimized}
              toggleMinimize={toggleMinimize}
              readOnly={readOnly}
            />
          </div>
        </div>
      </div>
    </EditingProvider>
  )
} 