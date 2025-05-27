import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs"
import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export async function GET(request: NextRequest) {
  try {
    const requestUrl = new URL(request.url)
    const code = requestUrl.searchParams.get("code")
    const inviteCode = requestUrl.searchParams.get("invite_code")
    const error = requestUrl.searchParams.get("error")
    const errorDescription = requestUrl.searchParams.get("error_description")
    const errorCode = requestUrl.searchParams.get("error_code")

    console.log('Auth callback received:', {
      code: code ? 'present' : 'missing',
      inviteCode,
      error,
      errorDescription,
      errorCode,
      fullUrl: request.url
    })

    // Handle errors from the URL first
    if (error) {
      console.error('Auth callback error:', { error, errorDescription, errorCode })
      
      let redirectUrl: URL
      let errorMessage = errorDescription || error
      
      // Handle specific error cases
      if (error === 'access_denied' && errorCode === 'otp_expired') {
        redirectUrl = new URL('/auth/link-expired', requestUrl.origin)
        redirectUrl.searchParams.set('message', 'Your invitation link has expired. Please request a new invitation.')
      } else if (error === 'access_denied') {
        redirectUrl = new URL('/login', requestUrl.origin)
        redirectUrl.searchParams.set('error', 'access_denied')
        redirectUrl.searchParams.set('message', 'Access denied. Please try logging in again.')
      } else {
        redirectUrl = new URL('/login', requestUrl.origin)
        redirectUrl.searchParams.set('error', error)
        redirectUrl.searchParams.set('message', errorMessage)
      }
      
      return NextResponse.redirect(redirectUrl)
    }

    // If no code is provided, redirect to login
    if (!code) {
      console.warn('Auth callback called without code parameter')
      const redirectUrl = new URL('/login', requestUrl.origin)
      redirectUrl.searchParams.set('error', 'missing_code')
      redirectUrl.searchParams.set('message', 'Authentication failed - missing authorization code')
      return NextResponse.redirect(redirectUrl)
    }

    const cookieStore = cookies()
    const supabase = createRouteHandlerClient({ cookies: () => cookieStore })

    // Exchange the code for a session
    const { data: authData, error: authError } = await supabase.auth.exchangeCodeForSession(code)

    if (authError) {
      console.error('Failed to exchange code for session:', authError.message)
      const redirectUrl = new URL('/login', requestUrl.origin)
      redirectUrl.searchParams.set('error', 'auth_failed')
      redirectUrl.searchParams.set('message', 'Authentication failed - please try again')
      return NextResponse.redirect(redirectUrl)
    }

    if (!authData.session || !authData.user) {
      console.error('No session or user returned after code exchange')
      const redirectUrl = new URL('/login', requestUrl.origin)
      redirectUrl.searchParams.set('error', 'no_session')
      redirectUrl.searchParams.set('message', 'Authentication failed - no session created')
      return NextResponse.redirect(redirectUrl)
    }

    console.log('Successfully authenticated user:', authData.user.email)

    // If this is an invite-based registration, redirect to register page with the code
    if (inviteCode) {
      console.log('Invite-based auth detected, redirecting to registration')
      const redirectUrl = new URL('/register', requestUrl.origin)
      redirectUrl.searchParams.set('code', inviteCode)
      return NextResponse.redirect(redirectUrl)
    }

    // For regular login, redirect to dashboard
    console.log('Regular login detected, redirecting to dashboard')
    const redirectUrl = new URL('/dashboard', requestUrl.origin)
    return NextResponse.redirect(redirectUrl)

  } catch (error: any) {
    console.error('Unexpected error in auth callback:', error)
    const requestUrl = new URL(request.url)
    const redirectUrl = new URL('/login', requestUrl.origin)
    redirectUrl.searchParams.set('error', 'unexpected_error')
    redirectUrl.searchParams.set('message', 'An unexpected error occurred during authentication')
    return NextResponse.redirect(redirectUrl)
  }
} 