import type { NextApiRequest, NextApiResponse } from 'next';
// Import the correct Auth Helper for Pages Router API Routes
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

  const { email, password } = req.body;

  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }

  // Create Supabase client specifically for Pages API routes
  const supabase = createPagesServerClient/*<Database>*/({ req, res }); // Pass req and res

  try {
    // Sign in using the Auth Helper client
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      console.error('Supabase sign in error:', error.message);
      // Provide a generic error message to the client for security
      return res.status(401).json({ error: 'Invalid login credentials' });
    }

    if (!data.user) {
        // This case should ideally be covered by the error above, but good to check
        console.error('Login successful but no user data returned.');
        return res.status(500).json({ error: 'Login failed, please try again.' });
    }

    // ---- IMPORTANT: Remove the manual cookie setting ----
    // The createPagesServerClient handles setting the auth cookies automatically
    // based on the successful signInWithPassword call.

    // Return success response (user data can be useful for the client)
    return res.status(200).json({
      success: true,
      user: {
        id: data.user.id,
        email: data.user.email,
        // Avoid sending sensitive info like session tokens back in the JSON body
      }
    });
  } catch (error: any) {
    console.error('Login API route error:', error);
    return res.status(500).json({ error: error.message || 'Internal server error during login' });
  }
} 