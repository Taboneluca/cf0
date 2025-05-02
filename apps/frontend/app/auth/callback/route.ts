import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs"
import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get("code")
  const inviteCode = requestUrl.searchParams.get("invite_code")

  if (code) {
    const cookieStore = cookies()
    const supabase = createRouteHandlerClient({ cookies: () => cookieStore })
    await supabase.auth.exchangeCodeForSession(code)
  }

  // If this is a waitlist invitation, forward to registration
  if (inviteCode) {
    return NextResponse.redirect(
      new URL(`/register?code=${inviteCode}`, request.url)
    )
  }

  // Default redirect for regular sign-ins
  return NextResponse.redirect(new URL("/dashboard", request.url))
}
