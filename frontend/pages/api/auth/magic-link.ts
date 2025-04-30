import type { NextApiRequest, NextApiResponse } from 'next';
import { createClient } from '@supabase/supabase-js';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { email } = req.body;
  
  if (!email) {
    return res.status(400).json({ error: 'Email is required' });
  }

  try {
    // Create a Supabase client with the service role key
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );

    // Send magic link email
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL || req.headers.origin}/auth/callback`,
      }
    });

    if (error) {
      return res.status(400).json({ error: error.message });
    }

    // Return success response
    return res.status(200).json({ 
      success: true,
      message: 'Magic link sent' 
    });
  } catch (error: any) {
    console.error('Magic link error:', error);
    return res.status(500).json({ error: error.message || 'Internal server error' });
  }
} 