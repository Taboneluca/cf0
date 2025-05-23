import type { ColumnDef } from "@tanstack/react-table"
import Link from "next/link"
import type { Workbook } from "@/types/database"

export const workbookColumns: ColumnDef<Workbook>[] = [
  { 
    header: "Title", 
    accessorKey: "title",
    cell: ({ row }) => (
      <Link href={`/workbook/${row.original.id}`} className="font-medium hover:underline">
        {row.original.title}
      </Link>
    )
  },
  { 
    header: "Updated",
    accessorFn: w => new Date(w.updated_at),
    cell: ({ getValue }) => getValue<Date>().toLocaleString()
  },
  { 
    header: "Visibility", 
    accessorKey: "is_public",
    cell: ({ getValue }) => getValue<boolean>() ? "Public" : "Private"
  },
] 