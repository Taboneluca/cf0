import type { NextApiRequest, NextApiResponse } from 'next';
import { createClient } from '@supabase/supabase-js';

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Create a Supabase client with the service role key
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!
    );

    // Get the current user's session from request cookies
    const accessToken = req.cookies['sb-access-token'];
    const refreshToken = req.cookies['sb-refresh-token'];
    
    if (!accessToken || !refreshToken) {
      return res.status(401).json({ error: 'No valid session tokens' });
    }

    // Create a new session using the refresh token
    const { data, error } = await supabase.auth.refreshSession({
      refresh_token: refreshToken,
    });

    if (error || !data.session) {
      return res.status(401).json({ error: 'Failed to refresh session' });
    }

    // Set cookies for the new session
    res.setHeader('Set-Cookie', [
      `sb-access-token=${data.session.access_token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${60 * 60 * 24 * 7}`,
      `sb-refresh-token=${data.session.refresh_token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${60 * 60 * 24 * 7}`,
    ]);

    return res.status(200).json({ success: true });
  } catch (error) {
    console.error('Failed to refresh session:', error);
    return res.status(500).json({ error: 'Internal server error' });
  }
} 