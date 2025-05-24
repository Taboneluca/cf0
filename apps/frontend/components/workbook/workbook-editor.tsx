"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Save } from "lucide-react"
import { supabase } from "@/lib/supabase/client"
import type { Workbook } from "@/types/database"
import SpreadsheetInterface from "../spreadsheet-interface"
import type { SpreadsheetData } from "@/types/spreadsheet"
import { useWorkbook } from "@/context/workbook-context"
import { backendSheetToUI, backendSheetToUIMap } from "@/utils/transform"
import { createSheet, fetchSheet } from "@/utils/backend"

interface WorkbookEditorProps {
  workbook: Workbook
  userId: string
}

export default function WorkbookEditor({ workbook, userId }: WorkbookEditorProps) {
  const [isSaving, setIsSaving] = useState(false)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)
  const router = useRouter()
  const [wb, dispatch] = useWorkbook()
  const { wid, active, data: workbookData, sheets } = wb

  // Track last auth retry timestamp to avoid excessive retries
  const [lastAuthRetry, setLastAuthRetry] = useState<number>(0)

  // Auto-save functionality
  useEffect(() => {
    const saveTimeout = setTimeout(async () => {
      await saveWorkbook()
    }, 5000) // Auto-save after 5 seconds of inactivity

    return () => clearTimeout(saveTimeout)
  }, [workbookData, sheets])

  const saveWorkbook = async () => {
    if (!workbookData || Object.keys(workbookData).length === 0) return;
    
    setIsSaving(true)

    try {
      // Authentication handling with improved error management and debouncing
      let isAuthenticated = false;
      
      try {
        // Check if user is authenticated - use getUser instead of getSession for better security
        const { data: { user } } = await supabase.auth.getUser();
        isAuthenticated = !!user;
        
        if (!isAuthenticated) {
          // Only attempt refresh if we haven't tried recently
          const now = Date.now();
          if (now - lastAuthRetry > 30000) { // 30 seconds between retries
            console.log("User not authenticated - attempting session refresh");
            setLastAuthRetry(now);
            
            // Try to refresh the session
            const { data: refreshData } = await supabase.auth.refreshSession();
            isAuthenticated = !!refreshData.user;
            
            if (!isAuthenticated) {
              console.log("Authentication refresh failed - skipping Supabase save");
            }
          } else {
            // Skip retry if we've tried recently
            console.log("Skipping auth retry (rate limited) - last attempt within 30s");
          }
        }
      } catch (authError) {
        console.error("Authentication error:", authError);
      }
      
      // Only try to save to Supabase if authenticated
      if (isAuthenticated) {
        await saveToSupabase();
      }

      // Save to backend API regardless of Supabase result
      try {
        await Promise.all(
          Object.entries(workbookData).map(([sid, sheetData]) => 
            // For each sheet with cells
            sheetData.cells && Object.keys(sheetData.cells).length > 0 ? 
              // Save each cell
              Promise.all(
                Object.entries(sheetData.cells).map(([cellId, cell]) => 
                  handleCellUpdate(cellId, cell.value, sid)
                )
              ) : Promise.resolve()
          )
        );
        
        setLastSaved(new Date())
      } catch (apiError) {
        console.error("Error saving to API:", apiError)
      }
    } catch (error) {
      console.error("Error in saveWorkbook:", error)
    } finally {
      setIsSaving(false)
    }
  }

  // Helper function to save to Supabase
  const saveToSupabase = async () => {
    try {
      const { error } = await supabase
        .from("spreadsheet_workbooks")
        .update({
          data: workbookData,
          sheets: sheets,  // Save the sheets array to persist empty sheets
          updated_at: new Date().toISOString(),
        })
        .eq("id", workbook.id)

      if (error) {
        console.error("Supabase save error:", error)
        if (error.code === "42501") { // Permission error
          console.log("Permissions issue - checking if user is authorized")
          if (workbook.user_id !== userId) {
            console.log("User does not own this workbook - skipping save to Supabase")
          }
        } else {
          throw error
        }
      }
    } catch (error) {
      console.error("Error saving to Supabase:", error)
    }
  }

  const handleCellUpdate = async (cellId: string, value: string, sheetId = active) => {
    try {
      // If the cell doesn't exist in our state yet, create it
      const cellExists = workbookData[sheetId]?.cells[cellId] !== undefined;
      
      // If value hasn't changed, skip the update to avoid unnecessary backend calls
      if (cellExists && workbookData[sheetId].cells[cellId].value === value) {
        return;
      }
      
      if (!cellExists) {
        const updatedData = {
          ...workbookData[sheetId],
          cells: { ...workbookData[sheetId].cells, [cellId]: { value } }
        };
        dispatch({
          type: "UPDATE_SHEET",
          sid: sheetId,
          data: updatedData
        });
      }
      
      // Send to backend
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/workbook/${wid}/sheet/${sheetId}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cell: cellId, value }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to update cell');
      }
      
      // Parse response and update state
      const result = await response.json();
      
      // Check if the response includes the updated sheet and all sheets
      if (result.sheet) {
        dispatch({
          type: "UPDATE_SHEET",
          sid: result.active || sheetId,
          data: backendSheetToUI(result.sheet)
        });
      }
      
      // If all_sheets data is included, merge it into the state
      if (result.all_sheets) {
        dispatch({
          type: "MERGE_SHEETS_DATA",
          data: backendSheetToUIMap(result.all_sheets)
        });
      }
    } catch (error) {
      console.error('Error updating cell:', error);
    }
  };

  const handleManualSave = () => {
    saveWorkbook()
  }

  const isOwner = workbook.user_id === userId

  return (
    <div className="flex flex-col h-screen">
      <header className="border-b bg-white py-2 px-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-gray-500 hover:text-gray-700">
              <ArrowLeft size={20} />
            </Link>
            <h1 className="text-lg font-medium">{workbook.title}</h1>
            {!isOwner && <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-600">View Only</span>}
          </div>
        </div>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-col flex-1">
          {/* Save controls above spreadsheet */}
          <div className="flex justify-end items-center gap-4 px-4 py-2 bg-gray-50 border-b">
            {isOwner && (
              <button
                onClick={handleManualSave}
                disabled={isSaving}
                className="flex items-center gap-1 rounded-md bg-blue-500 px-3 py-1 text-sm text-white hover:bg-blue-600 disabled:opacity-50"
              >
                <Save size={16} />
                {isSaving ? "Saving..." : "Save"}
              </button>
            )}
            {lastSaved && <span className="text-xs text-gray-500">Last saved: {lastSaved.toLocaleTimeString()}</span>}
          </div>
          <SpreadsheetInterface onDataChange={() => {}} readOnly={!isOwner} />
        </div>
      </div>
    </div>
  )
} 