import { redirect } from "next/navigation"
import { createServerComponentClient } from "@supabase/auth-helpers-nextjs"
import { cookies } from "next/headers"

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const cookieStore = cookies()
  const supabase = createServerComponentClient({ cookies: () => cookieStore })

  // Check if user is authenticated
  const { data: { session }, error: sessionError } = await supabase.auth.getSession()

  if (sessionError || !session) {
    redirect("/login?error=authentication_required")
  }

  // Check if user is admin
  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("is_admin")
    .eq("id", session.user.id)
    .single()

  if (profileError || !profile?.is_admin) {
    redirect("/dashboard?error=admin_access_required")
  }

  return (
    <div className="min-h-screen bg-black">
      <div className="border-b border-orange-500/30 bg-orange-500/10 p-4">
        <div className="container max-w-6xl mx-auto">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-semibold text-white">Admin Panel</h1>
              <p className="text-orange-200 text-sm">System administration and management</p>
            </div>
            <a 
              href="/dashboard" 
              className="text-orange-300 hover:text-orange-100 text-sm underline"
            >
              ← Back to Dashboard
            </a>
          </div>
        </div>
      </div>
      {children}
    </div>
  )
} 