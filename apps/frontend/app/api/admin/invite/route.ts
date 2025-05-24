import { NextResponse } from "next/server"
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs"
import { createClient } from "@supabase/supabase-js"
import { cookies } from "next/headers"

export async function POST(request: Request) {
  try {
    const { email } = await request.json()

    if (!email) {
      return NextResponse.json({ error: "Email is required" }, { status: 400 })
    }

    const cookieStore = cookies()
    const supabase = createRouteHandlerClient({ cookies: () => cookieStore })

    // Verify the user is an admin
    const { data: { session }, error: sessionError } = await supabase.auth.getSession()
    
    if (sessionError || !session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    // Check if user is admin
    const { data: profile, error: profileError } = await supabase
      .from("profiles")
      .select("is_admin")
      .eq("id", session.user.id)
      .single()

    if (profileError || !profile?.is_admin) {
      return NextResponse.json({ error: "Admin access required" }, { status: 403 })
    }

    // Create service role client for admin operations
    const serviceSupabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    )

    // Check if waitlist entry exists
    const { data: waitlistEntry, error: waitlistError } = await serviceSupabase
      .from("waitlist")
      .select("*")
      .eq("email", email)
      .single()

    if (waitlistError || !waitlistEntry) {
      return NextResponse.json({ error: "Waitlist entry not found" }, { status: 404 })
    }

    if (waitlistEntry.status !== "pending") {
      return NextResponse.json({ 
        error: `User is already ${waitlistEntry.status}` 
      }, { status: 400 })
    }

    // Use the invite_waitlist_user function to update status and get invite code
    const { data: inviteResult, error: inviteError } = await serviceSupabase
      .rpc("invite_waitlist_user", { user_email: email })

    if (inviteError) {
      console.error("RPC error:", inviteError)
      return NextResponse.json({ error: inviteError.message }, { status: 400 })
    }

    // Get the updated waitlist entry with invite code
    const { data: updatedEntry, error: fetchError } = await serviceSupabase
      .from("waitlist")
      .select("*")
      .eq("email", email)
      .single()

    if (fetchError) {
      console.error("Error fetching updated entry:", fetchError)
      return NextResponse.json({ error: "Failed to fetch updated entry" }, { status: 500 })
    }

    // Send invite email via Supabase Auth using service role
    const baseUrl = process.env.NODE_ENV === 'production' 
      ? 'https://cf0.ai'
      : process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'
    
    const redirectTo = `${baseUrl}/auth/callback?invite_code=${updatedEntry.invite_code}`

    const { error: authError } = await serviceSupabase.auth.admin.inviteUserByEmail(email, {
      redirectTo,
      data: { 
        waitlist: true, 
        invite_code: updatedEntry.invite_code 
      }
    })

    if (authError) {
      console.error("Auth invite error:", authError)
      // Revert the waitlist status change
      await serviceSupabase
        .from("waitlist")
        .update({ status: "pending", invited_at: null })
        .eq("email", email)
      
      return NextResponse.json({ error: authError.message }, { status: 400 })
    }

    return NextResponse.json({ 
      success: true,
      data: updatedEntry 
    })
  } catch (error) {
    console.error("Invite API error:", error)
    return NextResponse.json({ error: "An unexpected error occurred" }, { status: 500 })
  }
} 