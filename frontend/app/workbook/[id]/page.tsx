import { redirect } from "next/navigation"
import { createSupabaseServerComponentClient } from "@/lib/supabase/server"
import WorkbookEditor from "@/components/workbook/workbook-editor"
import { WorkbookProvider } from "@/context/workbook-context"

interface WorkbookPageProps {
  params: {
    id: string
  }
}

export default async function WorkbookPage({ params }: WorkbookPageProps) {
  const supabase = createSupabaseServerComponentClient()

  // Get session
  const {
    data: { session },
  } = await supabase.auth.getSession()

  // If no session, redirect to login
  if (!session) {
    redirect("/login")
  }

  // Get workbook
  const { data: workbook, error } = await supabase.from("workbooks").select("*").eq("id", params.id).single()

  // If workbook not found or not accessible, redirect to dashboard
  if (error || !workbook) {
    redirect("/dashboard")
  }

  // Check if user has access to this workbook
  if (workbook.user_id !== session.user.id && !workbook.is_public) {
    redirect("/dashboard")
  }

  return (
    <WorkbookProvider key={params.id}>
      <WorkbookEditor workbook={workbook} userId={session.user.id} />
    </WorkbookProvider>
  )
}
