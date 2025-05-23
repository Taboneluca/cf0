import { createMiddlewareClient } from '@supabase/auth-helpers-nextjs'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
// import type { Database } from '@/types_db'

export async function middleware(req: NextRequest) {
  // Clone the request headers for logging
  const requestHeaders = new Headers(req.headers)
  const userAgent = requestHeaders.get('user-agent') || 'unknown'
  
  // Create a new response right away
  const res = NextResponse.next()
  
  // Create a Supabase client configured to use cookies
  const supabase = createMiddlewareClient/*<Database>*/({ req, res })
  
  // Refresh session if expired - this will update the cookie
  const { data: { session }, error: sessionError } = await supabase.auth.getSession()
  
  if (sessionError) {
    console.error('Session error in middleware:', sessionError.message)
  }
  
  // Check the cookie header from the request
  const cookieHeader = req.headers.get('cookie') || ''
  const hasSupabaseCookie = cookieHeader.includes('sb-') || cookieHeader.includes('supabase-')
  
  // Log auth state for all protected routes
  const isProtectedRoute = req.nextUrl.pathname.startsWith('/dashboard') || 
                         req.nextUrl.pathname.startsWith('/workbook')
  
  if (isProtectedRoute) {
    console.log(`Auth middleware for ${req.nextUrl.pathname}:`, { 
      hasSession: !!session,
      hasSupabaseCookie,
      sessionExpiresAt: session?.expires_at ? new Date(session.expires_at * 1000).toISOString() : 'no-session',
      userAgent: userAgent.substring(0, 50) // Truncate for logging
    })
  }
  
  if (isProtectedRoute && !session) {
    console.log('Redirecting to login from protected route:', req.nextUrl.pathname)
    
    // Add a header to help debug redirects
    const redirectUrl = new URL('/login', req.url)
    redirectUrl.searchParams.set('from', req.nextUrl.pathname)
    
    // Set short cache to avoid excessive auth checks
    const response = NextResponse.redirect(redirectUrl)
    response.headers.set('Cache-Control', 'no-store, max-age=0')
    
    return response
  }
  
  // For all responses, ensure auth-related responses aren't cached
  res.headers.set('Cache-Control', 'no-store, max-age=0')
  
  return res
}

// Only run the middleware on these paths
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public (public files)
     * - api/auth (auth API endpoints that set cookies)
     */
    '/((?!_next/static|_next/image|favicon.ico|public|api/auth).*)',
    '/dashboard/:path*', // Explicitly match dashboard routes
    '/workbook/:path*',  // Explicitly match workbook routes
  ],
} 