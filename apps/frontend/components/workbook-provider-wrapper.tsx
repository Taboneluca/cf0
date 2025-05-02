"use client"

import { WorkbookProvider } from "@/context/workbook-context"

export default function WorkbookProviderWrapper({
  children,
}: {
  children: React.ReactNode
}) {
  return <WorkbookProvider>{children}</WorkbookProvider>
} 