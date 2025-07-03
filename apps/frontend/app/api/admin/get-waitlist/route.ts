import { NextResponse } from "next/server"
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs"
import { createClient } from "@supabase/supabase-js"
import { cookies } from "next/headers"

export async function GET() {
  try {
    const cookieStore = cookies()
    const supabase = createRouteHandlerClient({ cookies: () => cookieStore })

    // Verify the user is an admin
    const { data: { session }, error: sessionError } = await supabase.auth.getSession()
    
    if (sessionError || !session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    // Check if user is admin
    const { data: profile } = await supabase
      .from("profiles")
      .select("is_admin")
      .eq("id", session.user.id)
      .single()

    if (!profile?.is_admin) {
      return NextResponse.json({ error: "Admin access required" }, { status: 403 })
    }

    // Use service role client to get all waitlist entries (bypasses RLS)
    const serviceSupabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    )

    const { data: waitlistData, error: waitlistError } = await serviceSupabase
      .from("waitlist")
      .select("*")
      .order("created_at", { ascending: false })

    if (waitlistError) {
      console.error("Error fetching waitlist:", waitlistError)
      return NextResponse.json({ error: "Failed to fetch waitlist data" }, { status: 500 })
    }

    console.log(`Admin ${session.user.email} accessed waitlist data. Found ${waitlistData?.length || 0} entries`)

    return NextResponse.json({ 
      success: true, 
      data: waitlistData || [],
      total: waitlistData?.length || 0 
    })
  } catch (error) {
    console.error("Waitlist API error:", error)
    return NextResponse.json({ error: "An unexpected error occurred" }, { status: 500 })
  }
} 