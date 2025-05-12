import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Set up an auth state change listener to handle token refresh failures
// This helps prevent the "User not authenticated" errors in the console
if (typeof window !== 'undefined') {
  supabase.auth.onAuthStateChange(async (event, session) => {
    // Handle session expiration or refresh failures
    if (event === 'SIGNED_OUT' || event === 'USER_UPDATED') {
      console.log('Auth state change detected, refreshing session')
      try {
        const { error } = await supabase.auth.refreshSession()
        if (error) {
          console.log('Session refresh failed, attempting anonymous auth')
          await supabase.auth.signInAnonymously()
        }
      } catch (err) {
        console.error('Failed to refresh authentication:', err)
      }
    }
  })
}
