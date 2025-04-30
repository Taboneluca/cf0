"use client"

import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import type { Workbook } from "@/types/database"

interface WorkbookListProps {
  workbooks: Workbook[]
}

export function WorkbookList({ workbooks }: WorkbookListProps) {
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
          className="group flex flex-col rounded-lg border p-4 transition-all hover:border-blue-200 hover:shadow-sm"
        >
          <div className="mb-2 flex items-center justify-between">
            <h3 className="font-medium group-hover:text-blue-600">{workbook.title}</h3>
            {workbook.is_public && (
              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-600">Public</span>
            )}
          </div>
          <p className="mb-4 text-sm text-gray-500 line-clamp-2">{workbook.description || "No description"}</p>
          <div className="mt-auto text-xs text-gray-400">
            Updated {formatDistanceToNow(new Date(workbook.updated_at), { addSuffix: true })}
          </div>
        </Link>
      ))}
    </div>
  )
}
