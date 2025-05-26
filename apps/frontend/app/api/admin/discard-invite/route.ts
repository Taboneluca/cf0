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
        error: `Cannot discard invite for user with status: ${waitlistEntry.status}` 
      }, { status: 400 })
    }

    // Reset the waitlist entry to pending status
    const { error: updateError } = await serviceSupabase
      .from("waitlist")
      .update({ 
        status: "pending", 
        invited_at: null,
        invite_code: null
      })
      .eq("email", email)

    if (updateError) {
      console.error("Error discarding invite:", updateError)
      return NextResponse.json({ error: updateError.message }, { status: 500 })
    }

    // Also delete the user from auth.users if they were created by the invite
    // This prevents "user already exists" errors when re-inviting
    try {
      const { error: deleteUserError } = await serviceSupabase.auth.admin.deleteUser(
        waitlistEntry.invite_code || '' // Use invite_code as temporary identifier
      )
      
      // If that doesn't work, try to find and delete by email
      if (deleteUserError) {
        const { data: authUsers } = await serviceSupabase.auth.admin.listUsers()
        const userToDelete = authUsers.users?.find(u => u.email === email)
        
        if (userToDelete) {
          await serviceSupabase.auth.admin.deleteUser(userToDelete.id)
        }
      }
    } catch (authError) {
      // Don't fail the discard if we can't delete the auth user
      console.warn("Could not delete auth user (may not exist):", authError)
    }

    return NextResponse.json({ 
      success: true,
      message: "Invite discarded successfully",
      data: { 
        email,
        status: "pending"
      }
    })
  } catch (error) {
    console.error("Discard invite API error:", error)
    return NextResponse.json({ error: "An unexpected error occurred" }, { status: 500 })
  }
} 