import type { NextApiRequest, NextApiResponse } from 'next';
import { createPagesServerClient } from '@supabase/auth-helpers-nextjs';
// import type { Database } from '@/types_db'; // Uncomment if using generated types

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST']);
    return res.status(405).json({ error: `Method ${req.method} Not Allowed` });
  }

  try {
    // Create Supabase client specifically for Pages API routes
    const supabase = createPagesServerClient/*<Database>*/({ req, res });
    
    // Get the current session
    const { data: { session }, error } = await supabase.auth.getSession();
    
    if (error) {
      console.error('Session sync error:', error.message);
      return res.status(401).json({ error: 'Authentication error' });
    }
    
    if (!session) {
      console.log('No valid session found in session-sync');
      return res.status(401).json({ error: 'No valid session' });
    }
    
    // Session exists and is valid
    console.log('Session sync successful, cookies set');
    
    // Set stronger cache control to prevent caching auth responses
    res.setHeader('Cache-Control', 'private, no-cache, no-store, must-revalidate, max-age=0');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
    
    // Return minimal user info
    return res.status(200).json({
      user: {
        id: session.user.id,
        email: session.user.email,
      },
      session: {
        expires_at: session.expires_at
      }
    });
  } catch (error: any) {
    console.error('Session sync error:', error.message);
    return res.status(500).json({ error: 'Internal server error during session sync' });
  }
} 