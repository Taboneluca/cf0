import { NextResponse } from "next/server"
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs"
import { cookies } from "next/headers"

export async function GET() {
  try {
    const cookieStore = cookies()
    const supabase = createRouteHandlerClient({ cookies: () => cookieStore })

    // Get current session
    const { data: { session }, error: sessionError } = await supabase.auth.getSession()
    
    if (sessionError || !session) {
      return NextResponse.json({ 
        error: "No session found",
        sessionError: sessionError?.message,
        hasSession: false 
      })
    }

    // Try to get profile data
    const { data: profile, error: profileError } = await supabase
      .from("profiles")
      .select("id, email, is_admin, is_verified, is_waitlisted")
      .eq("id", session.user.id)
      .single()

    return NextResponse.json({
      session: {
        userId: session.user.id,
        email: session.user.email,
        expiresAt: session.expires_at
      },
      profile: profile,
      profileError: profileError?.message,
      isAdmin: profile?.is_admin || false,
      timestamp: new Date().toISOString()
    })
  } catch (error: any) {
    console.error("Admin check debug error:", error)
    return NextResponse.json({ 
      error: "Unexpected error", 
      message: error.message 
    }, { status: 500 })
  }
} 