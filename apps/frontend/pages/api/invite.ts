import type { NextApiRequest, NextApiResponse } from 'next';
import { createClient } from '@supabase/supabase-js';

const sb = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const { email } = req.body;
  if (!email) {
    return res.status(400).json({ error: 'Email is required' });
  }

  try {
    // 1) Get the updated waitlist row from our database function
    const { data: updatedEntry, error: rpcError } = await sb
      .rpc('invite_waitlist_user', { user_email: email })
      .single();

    if (rpcError) {
      console.error('RPC error:', rpcError);
      return res.status(400).json({ error: rpcError.message || rpcError });
    }

    // Cast the updatedEntry to include invite_code
    const entryData = updatedEntry as { invite_code: string };
    const redirectTo = `${SITE_URL}/auth/callback?invite_code=${entryData.invite_code}`;

    // 2) Send invite email via Supabase Auth API
    const { error: authErr } = await sb.auth.admin.inviteUserByEmail(email, {
      redirectTo,
      data: { waitlist: true, invite_code: entryData.invite_code }
    });

    if (authErr) {
      console.error('Auth error:', authErr);
      return res.status(400).json({ error: authErr.message || authErr });
    }

    // 3) Return success response with the updated entry
    return res.status(200).json({ 
      success: true,
      data: updatedEntry
    });

  } catch (error: any) {
    console.error('Unexpected error:', error);
    return res.status(500).json({ error: error.message || 'An unexpected error occurred' });
  }
}
