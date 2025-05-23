import { redirect } from "next/navigation"
import { createSupabaseServerComponentClient } from "@/lib/supabase/server"
import WorkbookEditor from "@/components/workbook/workbook-editor"
import { WorkbookProvider } from "@/context/workbook-context"

export default async function WorkbookPage({ 
  params 
}: { 
  params: Promise<{ id: string }> | { id: string }
}) {
  const { id: wid } = await params;
  
  const supabase = createSupabaseServerComponentClient()
  
  const { data: { session } } = await supabase.auth.getSession()

  if (!session) {
    redirect("/login")
  }

  const { data: workbook, error } = await supabase.from("workbooks").select("*").eq("id", wid).single()

  if (error || !workbook) {
    redirect("/dashboard")
  }

  if (workbook.user_id !== session.user.id && !workbook.is_public) {
    redirect("/dashboard")
  }

  return (
    <WorkbookProvider key={wid}>
      <WorkbookEditor workbook={workbook} userId={session.user.id} />
    </WorkbookProvider>
  )
}
