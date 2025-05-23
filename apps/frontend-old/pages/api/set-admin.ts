import type { NextApiRequest, NextApiResponse } from 'next';
import { createClient } from '@supabase/supabase-js';

const sb = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  // This should be protected with proper auth
  // For example, check an auth header with admin token or session cookie
  const adminToken = req.headers.authorization?.split(' ')[1];
  if (adminToken !== process.env.ADMIN_SECRET_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const { userId, isAdmin = true } = req.body;
  if (!userId) {
    return res.status(400).json({ error: 'User ID is required' });
  }

  try {
    // Update the user's admin status
    const { error } = await sb
      .from('profiles')
      .update({ is_admin: isAdmin })
      .eq('id', userId);

    if (error) throw error;

    return res.status(200).json({ success: true });
  } catch (error: any) {
    console.error('Error setting admin status:', error);
    return res.status(500).json({ error: error.message || 'An error occurred' });
  }
} 