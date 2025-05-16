import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables')
}

// Create client with improved session handling
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    storage: typeof window !== 'undefined' ? localStorage : undefined
  }
})

// Set up an auth state change listener to handle token refresh failures
// This helps prevent the "User not authenticated" errors in the console
if (typeof window !== 'undefined') {
  // Debug auth status
  supabase.auth.getSession().then(({ data }) => {
    console.log('Current auth status:', {
      isAuthenticated: !!data.session,
      expires: data.session?.expires_at ? new Date(data.session.expires_at * 1000).toISOString() : 'no-session'
    })
  })

  supabase.auth.onAuthStateChange(async (event, session) => {
    console.log('Auth state change:', event)
    
    // Handle session expiration or refresh failures
    if (event === 'SIGNED_OUT' || event === 'USER_UPDATED' || event === 'TOKEN_REFRESHED') {
      console.log('Auth state change detected, refreshing session')
      try {
        const { error } = await supabase.auth.refreshSession()
        if (error) {
          console.log('Session refresh failed, attempting to get current session')
          await supabase.auth.getSession()
        }
      } catch (err) {
        console.error('Failed to refresh authentication:', err)
      }
    }
  })
}
