import { NextResponse } from "next/server"
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs"
import { createClient } from "@supabase/supabase-js"
import { cookies } from "next/headers"

export async function DELETE(request: Request) {
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

    // Delete from auth.users first if they exist
    try {
      const { data: authUsers } = await serviceSupabase.auth.admin.listUsers()
      const userToDelete = authUsers.users?.find(u => u.email === email)
      
      if (userToDelete) {
        console.log(`Deleting auth user: ${email}`)
        await serviceSupabase.auth.admin.deleteUser(userToDelete.id)
      }
    } catch (authError) {
      console.warn("Could not delete auth user (may not exist):", authError)
    }

    // Delete from waitlist
    const { error: deleteError } = await serviceSupabase
      .from("waitlist")
      .delete()
      .eq("email", email)

    if (deleteError) {
      console.error("Error deleting waitlist user:", deleteError)
      return NextResponse.json({ error: deleteError.message }, { status: 500 })
    }

    return NextResponse.json({ 
      success: true,
      message: "User completely deleted from system",
      data: { 
        email,
        action: "deleted"
      }
    })
  } catch (error) {
    console.error("Delete waitlist user API error:", error)
    return NextResponse.json({ error: "An unexpected error occurred" }, { status: 500 })
  }
} 