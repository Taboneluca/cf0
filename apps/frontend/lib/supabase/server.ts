// Purpose: Exports Supabase client initializers for SERVER-SIDE use in Next.js App Router.

import { createServerComponentClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'

// If you have database types generated (e.g., from 'supabase gen types typescript'), import them
// import type { Database } from "@/types_db"; // Adjust path as needed

// Client for use in Server Components, Pages, Layouts (Server Side Rendering)
export function createServerClient() {
  const cookieStore = cookies()
  
  // Check environment variables are set
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  
  if (!supabaseUrl || !supabaseKey) {
    console.error('Missing Supabase environment variables');
    throw new Error('Missing Supabase environment variables')
  }
  
  // Use the official Next.js helper which handles cookie management correctly
  return createServerComponentClient({ cookies: () => cookieStore })
}

// Export with the original name for compatibility with existing code
export const createSupabaseServerComponentClient = createServerClient

// Don't initialize at module level - this causes cookies() to be called outside request context
// Instead, call the function directly when needed
// export const supabaseServer = createServerClient() 