"use client"

import { useState } from "react"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import type { Workbook } from "@/types/database"
import { Trash2 } from 'lucide-react'
import { supabase } from "@/lib/supabase/client"

interface WorkbookListProps {
  workbooks: Workbook[]
}

export function WorkbookList({ workbooks: initialWorkbooks }: WorkbookListProps) {
  const [workbooks, setWorkbooks] = useState<Workbook[]>(initialWorkbooks)

  // Add deleteWorkbook function
  const deleteWorkbook = async (id: string, e: React.MouseEvent) => {
    e.preventDefault() // Stop link navigation
    e.stopPropagation() // Prevent event bubbling
    
    if (!confirm('Are you sure you want to delete this workbook?')) {
      return
    }
    
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/workbook/${id}`, {
        method: 'DELETE',
      })
      
      if (response.ok) {
        // Remove from Supabase
        await supabase.from('workbooks').delete().eq('id', id)
        
        // Update local state to remove the deleted workbook
        setWorkbooks(workbooks.filter(w => w.id !== id))
      } else {
        console.error('Failed to delete workbook from backend')
      }
    } catch (error) {
      console.error('Error deleting workbook:', error)
    }
  }

  if (workbooks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
        <h3 className="mb-2 text-lg font-medium">No workbooks yet</h3>
        <p className="mb-6 text-sm text-gray-500">Create your first workbook to get started.</p>
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {workbooks.map((workbook) => (
        <Link
          key={workbook.id}
          href={`/workbook/${workbook.id}`}
          className="group relative flex flex-col rounded-lg border p-4 transition-all hover:border-blue-200 hover:shadow-sm"
        >
          <div className="mb-2 flex items-center justify-between">
            <h3 className="font-medium group-hover:text-blue-600">{workbook.title}</h3>
            {workbook.is_public && (
              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-600">Public</span>
            )}
          </div>
          <p className="mb-4 text-sm text-gray-500 line-clamp-2">{workbook.description || "No description"}</p>
          <div className="mt-auto flex justify-between items-center">
            <span className="text-xs text-gray-400">
              Updated {formatDistanceToNow(new Date(workbook.updated_at), { addSuffix: true })}
            </span>
            <button
              onClick={(e) => deleteWorkbook(workbook.id, e)}
              className="p-1 text-gray-400 hover:text-red-500 transition-colors"
              title="Delete workbook"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </Link>
      ))}
    </div>
  )
}
