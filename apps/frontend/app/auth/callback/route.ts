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

    console.log('Auth callback received:', {
      code: code ? 'present' : 'missing',
      inviteCode,
      error,
      errorDescription,
      fullUrl: request.url
    })

    // Handle errors from the URL
    if (error) {
      console.error('Auth callback error:', error, errorDescription)
      
      // If it's an expired link, redirect to a more helpful page
      if (error === 'access_denied' && errorDescription?.includes('expired')) {
        return NextResponse.redirect(
          new URL(`/auth/link-expired?message=${encodeURIComponent('Your invitation link has expired. Please contact support for a new invitation.')}`, request.url)
        )
      }
      
      // For other errors, redirect to login with error
      return NextResponse.redirect(
        new URL(`/login?error=${encodeURIComponent(error)}&message=${encodeURIComponent(errorDescription || 'Authentication failed')}`, request.url)
      )
    }

    if (code) {
      const cookieStore = cookies()
      const supabase = createRouteHandlerClient({ cookies: () => cookieStore })
      
      console.log('Attempting to exchange code for session...')
      const { data, error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)
      
      if (exchangeError) {
        console.error('Session exchange error:', exchangeError)
        
        // Handle specific exchange errors
        if (exchangeError.message?.includes('expired')) {
          return NextResponse.redirect(
            new URL(`/auth/link-expired?message=${encodeURIComponent('Your invitation link has expired. Please contact support for a new invitation.')}`, request.url)
          )
        }
        
        return NextResponse.redirect(
          new URL(`/login?error=session_error&message=${encodeURIComponent(exchangeError.message)}`, request.url)
        )
      }

      console.log('Session exchange successful:', {
        userId: data.user?.id,
        email: data.user?.email
      })
    }

    // If this is a waitlist invitation, forward to registration
    if (inviteCode) {
      console.log('Redirecting to registration with invite code:', inviteCode)
      return NextResponse.redirect(
        new URL(`/register?code=${inviteCode}`, request.url)
      )
    }

    // Default redirect for regular sign-ins
    console.log('Redirecting to dashboard')
    return NextResponse.redirect(new URL("/dashboard", request.url))

  } catch (error) {
    console.error('Auth callback unexpected error:', error)
    return NextResponse.redirect(
      new URL(`/login?error=callback_error&message=${encodeURIComponent('An unexpected error occurred during authentication')}`, request.url)
    )
  }
} 