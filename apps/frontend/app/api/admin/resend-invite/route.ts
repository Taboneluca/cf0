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

    // Check if waitlist entry exists and is invited
    const { data: waitlistEntry, error: waitlistError } = await serviceSupabase
      .from("waitlist")
      .select("*")
      .eq("email", email)
      .single()

    if (waitlistError || !waitlistEntry) {
      return NextResponse.json({ error: "Waitlist entry not found" }, { status: 404 })
    }

    if (waitlistEntry.status !== "invited") {
      return NextResponse.json({ 
        error: `User status is ${waitlistEntry.status}, can only resend to invited users` 
      }, { status: 400 })
    }

    if (!waitlistEntry.invite_code) {
      return NextResponse.json({ 
        error: "No invite code found for this user" 
      }, { status: 400 })
    }

    // Resend invite email via Supabase Auth using service role with correct URL
    const baseUrl = process.env.NODE_ENV === 'production' 
      ? 'https://cf0.ai'
      : process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000'
    
    const redirectTo = `${baseUrl}/auth/callback?invite_code=${waitlistEntry.invite_code}`

    const { error: authError } = await serviceSupabase.auth.admin.inviteUserByEmail(email, {
      redirectTo,
      data: { 
        waitlist: true, 
        invite_code: waitlistEntry.invite_code 
      }
    })

    if (authError) {
      console.error("Auth resend error:", authError)
      return NextResponse.json({ error: authError.message }, { status: 400 })
    }

    // Update the invited_at timestamp to reflect the resend
    const { error: updateError } = await serviceSupabase
      .from("waitlist")
      .update({ invited_at: new Date().toISOString() })
      .eq("email", email)

    if (updateError) {
      console.error("Error updating invited_at:", updateError)
      // Don't fail the request for this, just log it
    }

    return NextResponse.json({ 
      success: true,
      message: "Invite resent successfully",
      data: { 
        email,
        redirectTo,
        invited_at: new Date().toISOString()
      }
    })
  } catch (error) {
    console.error("Resend invite API error:", error)
    return NextResponse.json({ error: "An unexpected error occurred" }, { status: 500 })
  }
} 