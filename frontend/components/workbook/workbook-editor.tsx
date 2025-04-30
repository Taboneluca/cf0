"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Save } from "lucide-react"
import { supabase } from "@/lib/supabase/client"
import type { Workbook } from "@/types/database"
import SpreadsheetInterface from "@/components/spreadsheet-interface"
import type { SpreadsheetData } from "@/types/spreadsheet"
import { useWorkbook } from "@/context/workbook-context"

interface WorkbookEditorProps {
  workbook: Workbook
  userId: string
}

export default function WorkbookEditor({ workbook, userId }: WorkbookEditorProps) {
  const [isSaving, setIsSaving] = useState(false)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)
  const router = useRouter()
  const [wb] = useWorkbook()
  const { wid, active, data: workbookData, sheets } = wb

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
      // Check if user is authenticated
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        console.log("User not authenticated - skipping save")
        return
      }

      // Save to Supabase (as backup storage)
      const { error } = await supabase
        .from("workbooks")
        .update({
          data: workbookData,
          sheets: sheets,  // Save the sheets array to persist empty sheets
          updated_at: new Date().toISOString(),
        })
        .eq("id", workbook.id)
        .throwOnError()

      if (error) throw error

      // Also save all sheets to the backend engine
      await Promise.all(
        Object.entries(workbookData).map(([sid, sheetData]) => 
          // For each sheet with cells
          sheetData.cells && Object.keys(sheetData.cells).length > 0 ? 
            // Save each cell
            Promise.all(
              Object.entries(sheetData.cells).map(([cellId, cell]) => 
                fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/workbook/${wid}/sheet/${sid}/update`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ cell: cellId, value: cell.value })
                })
              )
            ) : Promise.resolve()
        )
      );

      setLastSaved(new Date())
    } catch (error) {
      console.error("Error saving workbook:", error)
    } finally {
      setIsSaving(false)
    }
  }

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
          <div className="flex items-center gap-4">
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
        </div>
      </header>
      <SpreadsheetInterface onDataChange={() => {}} readOnly={!isOwner} />
    </div>
  )
}
