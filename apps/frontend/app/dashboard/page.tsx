import { redirect } from "next/navigation"
import { createSupabaseServerComponentClient } from "@/lib/supabase/server"
import { WorkbookList } from "@/components/dashboard/workbook-list"
import { CreateWorkbookButton } from "@/components/dashboard/create-workbook-button"

export default async function DashboardPage() {
  const supabase = createSupabaseServerComponentClient()

  // Add detailed session debugging
  const { data: sessionData } = await supabase.auth.getSession()
  console.log("Dashboard session check:", { 
    hasSession: !!sessionData.session,
    sessionExpiry: sessionData.session?.expires_at ? new Date(sessionData.session.expires_at * 1000).toISOString() : 'no-session'
  })

  // Use getUser() for security
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser()

  // If no user or error, redirect to login
  if (userError || !user) {
    console.error("Error fetching user or user not found:", userError?.message || "Auth session missing!")
    redirect("/login?error=authentication_failed")
    return null
  }

  console.log("User authenticated successfully:", { 
    userId: user.id, 
    email: user.email 
  })

  // Get user's workbooks using the authenticated user ID
  const { data: workbooks, error: workbooksError } = await supabase
    .from("workbooks")
    .select("*")
    .eq("user_id", user.id)
    .order("updated_at", { ascending: false })

  if (workbooksError) {
    console.error("Error fetching workbooks:", workbooksError.message)
    // Handle error appropriately - proceeding with empty list
  }

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Your Workbooks</h1>
        <CreateWorkbookButton userId={user.id} />
      </div>
      <WorkbookList workbooks={workbooks || []} />
    </>
  )
}
