import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

// Handle missing environment variables gracefully during build time
let supabase: ReturnType<typeof createClient>

if (!supabaseUrl || !supabaseAnonKey) {
  if (typeof window === 'undefined') {
    // During build time, create a dummy client
    console.warn('Missing Supabase environment variables during build time - using fallback')
    supabase = createClient('https://placeholder.supabase.co', 'placeholder-key')
  } else {
    // At runtime, throw error
    throw new Error('Missing Supabase environment variables')
  }
} else {
  // Create client with improved session handling
  supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      // Always use localStorage - sessionStorage clears on refresh
      storage: typeof window !== 'undefined' ? localStorage : undefined
    }
  })
}

// Create function to get the current user ID that ensures we have a valid session
export async function getCurrentUserId() {
  if (typeof window === 'undefined') return null;
  
  try {
    // Try to get session
    const { data } = await supabase.auth.getSession();
    
    // If no session, try to refresh it
    if (!data.session) {
      const { error } = await supabase.auth.refreshSession();
      if (error) {
        console.error("Session refresh failed:", error.message);
        return null;
      }
      
      // Get session again after refresh
      const { data: refreshData } = await supabase.auth.getSession();
      return refreshData.session?.user?.id || null;
    }
    
    return data.session?.user?.id || null;
  } catch (err) {
    console.error("Error getting user ID:", err);
    return null;
  }
}

// Set up an auth state change listener to handle token refresh failures
// This helps prevent the "User not authenticated" errors in the console
if (typeof window !== 'undefined') {
  // Debug auth status
  supabase.auth.getSession().then(({ data }) => {
    console.log('Current auth status:', {
      isAuthenticated: !!data.session,
      userId: data.session?.user?.id,
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

export { supabase } 