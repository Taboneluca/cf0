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
        error: `User status is ${waitlistEntry.status}, can only withdraw invited users` 
      }, { status: 400 })
    }

    // Update waitlist status back to pending (withdraw the invite)
    const { error: updateError } = await serviceSupabase
      .from("waitlist")
      .update({ 
        status: "pending",
        invited_at: null,
        invite_code: null
      })
      .eq("email", email)

    if (updateError) {
      console.error("Error withdrawing invite:", updateError)
      return NextResponse.json({ error: updateError.message }, { status: 500 })
    }

    // Try to delete the auth user if they exist (since invite is withdrawn)
    try {
      const { data: authUsers } = await serviceSupabase.auth.admin.listUsers()
      const userToDelete = authUsers.users?.find(u => u.email === email)
      
      if (userToDelete) {
        console.log(`Deleting auth user for withdrawn invite: ${email}`)
        await serviceSupabase.auth.admin.deleteUser(userToDelete.id)
      }
    } catch (authError) {
      console.warn("Could not delete auth user (may not exist):", authError)
      // Don't fail the request for this
    }

    return NextResponse.json({ 
      success: true,
      message: "Invite withdrawn successfully",
      data: { 
        email,
        status: "pending"
      }
    })
  } catch (error) {
    console.error("Withdraw invite API error:", error)
    return NextResponse.json({ error: "An unexpected error occurred" }, { status: 500 })
  }
} 