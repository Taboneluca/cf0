import { createMiddlewareClient } from '@supabase/auth-helpers-nextjs'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
// import type { Database } from '@/types_db'

export async function middleware(req: NextRequest) {
  const res = NextResponse.next()
  
  // Create a Supabase client configured to use cookies
  const supabase = createMiddlewareClient/*<Database>*/({ req, res })
  
  // Refresh session if expired - this will update the cookie
  const { data: { session } } = await supabase.auth.getSession()
  
  // Check if accessing a protected route
  const isProtectedRoute = req.nextUrl.pathname.startsWith('/dashboard')
  
  if (isProtectedRoute && !session) {
    // Add debugging to help track down auth issues
    console.log('Auth session missing for protected route: ', req.nextUrl.pathname)
    
    // Redirect to login if accessing protected route without session
    const redirectUrl = new URL('/login', req.url)
    return NextResponse.redirect(redirectUrl)
  }
  
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
     */
    '/((?!_next/static|_next/image|favicon.ico|public).*)',
    '/dashboard/:path*', // Explicitly match dashboard routes
  ],
} 