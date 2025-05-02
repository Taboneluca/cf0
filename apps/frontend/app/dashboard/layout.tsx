import { redirect } from "next/navigation"
import { createSupabaseServerComponentClient } from "@/lib/supabase/server"
import { DashboardHeader } from "@/components/dashboard/dashboard-header"

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = createSupabaseServerComponentClient()

  // Use getUser() to get authenticated user
  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser()

  // Handle potential errors fetching the user
  if (userError) {
    console.error("DashboardLayout: Error fetching user:", userError.message)
    redirect("/login?error=authentication_error")
    return null
  }

  // If no user, redirect to login
  if (!user) {
    console.log("DashboardLayout: No user found, redirecting to login")
    redirect("/login?error=authentication_required")
    return null
  }

  // User is authenticated, proceed to get profile
  console.log("DashboardLayout: User authenticated:", user.id)

  // Check if user is an admin
  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("is_admin")
    .eq("id", user.id) // Use the authenticated user.id
    .single()

  if (profileError) {
    console.error("DashboardLayout: Error fetching profile:", profileError.message)
    // Handle profile fetch error - maybe assume not admin
  }

  const isAdmin = profile?.is_admin === true
  console.log("DashboardLayout: Profile fetched, isAdmin:", isAdmin)

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader user={user} isAdmin={isAdmin} />
      <main className="flex-1 container py-6">
        {children}
      </main>
    </div>
  )
} 