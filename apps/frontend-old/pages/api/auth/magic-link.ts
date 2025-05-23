import type { NextApiRequest, NextApiResponse } from 'next';
import { createPagesServerClient } from '@supabase/auth-helpers-nextjs';

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

  console.log(`Magic link requested for: ${email.substring(0, 3)}...`);

  try {
    // Use the same auth helper for consistent cookie handling
    const supabase = createPagesServerClient({ req, res });
    
    // Log important environment values to debug redirects
    console.log('Site URL:', process.env.NEXT_PUBLIC_SITE_URL || req.headers.origin);
    
    // Send magic link email
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL || req.headers.origin}/auth/callback`,
      }
    });

    if (error) {
      console.error('Magic link error:', error.message);
      return res.status(400).json({ error: error.message });
    }

    console.log('Magic link sent successfully');

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