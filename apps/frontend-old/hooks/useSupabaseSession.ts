"use client"

import { useState, useEffect } from 'react'
import { Session } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase/client'

export default function useSupabaseSession() {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, newSession) => {
      setSession(newSession)
      
      // Handle token refresh failure
      if (event === 'TOKEN_REFRESH_FAILED' as any) {
        console.log('Token refresh failed, attempting anonymous auth')
        // Silently try to sign in anonymously or with a basic provider
        supabase.auth.signInAnonymously().catch(err => {
          console.error('Failed to sign in anonymously:', err)
        })
      }
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [])

  return { session, loading }
} 