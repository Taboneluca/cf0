import { NextResponse } from "next/server"
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs"
import { createClient } from "@supabase/supabase-js"
import { cookies } from "next/headers"

export async function POST(request: Request) {
  try {
    const { inviteCode, email } = await request.json()

    if (!inviteCode || !email) {
      return NextResponse.json({ error: "Invite code and email are required" }, { status: 400 })
    }

    const cookieStore = cookies()
    const supabase = createRouteHandlerClient({ cookies: () => cookieStore })

    // Verify the user is authenticated (they just registered)
    const { data: { session }, error: sessionError } = await supabase.auth.getSession()
    
    if (sessionError || !session) {
      return NextResponse.json({ error: "User must be authenticated" }, { status: 401 })
    }

    // Verify the authenticated user's email matches the request
    if (session.user.email !== email) {
      return NextResponse.json({ error: "Email mismatch" }, { status: 403 })
    }

    // Use service role client to update waitlist (authenticated users can't update waitlist directly)
    const serviceSupabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    )

    // Verify the invite code belongs to this user and is in 'invited' status
    const { data: waitlistEntry, error: waitlistError } = await serviceSupabase
      .from("waitlist")
      .select("*")
      .eq("invite_code", inviteCode)
      .eq("email", email)
      .single()

    if (waitlistError || !waitlistEntry) {
      console.error("Waitlist verification failed:", waitlistError)
      return NextResponse.json({ error: "Invalid invite code or email" }, { status: 400 })
    }

    if (waitlistEntry.status !== "invited") {
      return NextResponse.json({ 
        error: "Invite code is not in the correct status for registration completion" 
      }, { status: 400 })
    }

    // Update waitlist status to converted
    const { error: updateError } = await serviceSupabase
      .from("waitlist")
      .update({ status: "converted" })
      .eq("invite_code", inviteCode)
      .eq("email", email)

    if (updateError) {
      console.error("Error updating waitlist status:", updateError)
      return NextResponse.json({ error: "Failed to update waitlist status" }, { status: 500 })
    }

    // Update user profile to mark them as no longer waitlisted and verified
    const { error: profileUpdateError } = await serviceSupabase
      .from("profiles")
      .update({ 
        is_waitlisted: false, 
        is_verified: true 
      })
      .eq("id", session.user.id)
      .eq("email", email)

    if (profileUpdateError) {
      console.error("Error updating profile:", profileUpdateError)
      // Don't fail the request for this - the main goal (waitlist update) succeeded
    }

    console.log(`Registration completed successfully for user ${email}`)

    return NextResponse.json({ 
      success: true,
      message: "Registration completed successfully" 
    })
  } catch (error) {
    console.error("Complete registration API error:", error)
    return NextResponse.json({ error: "An unexpected error occurred" }, { status: 500 })
  }
} 