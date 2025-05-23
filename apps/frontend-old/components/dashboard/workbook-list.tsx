"use client"

import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import type { Workbook } from "@/types/database"
import { Trash2 } from 'lucide-react'
import { supabase } from "@/lib/supabase/client"
import { DataTable } from "@/components/ui/data-table"
import { workbookColumns } from "./workbook-columns"

interface WorkbookListProps {
  workbooks: Workbook[]
}

export function WorkbookList({ workbooks: initialWorkbooks }: WorkbookListProps) {
  if (initialWorkbooks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
        <h3 className="mb-2 text-lg font-medium">No workbooks yet</h3>
        <p className="mb-6 text-sm text-gray-500">Create your first workbook to get started.</p>
      </div>
    )
  }

  return (
    <DataTable columns={workbookColumns} data={initialWorkbooks} pageSize={10} />
  )
}
