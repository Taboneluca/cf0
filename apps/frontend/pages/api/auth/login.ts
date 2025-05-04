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

  console.log(`Login attempt for email: ${email.substring(0, 3)}...`);
  
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

    console.log('Login successful for user ID:', data.user.id);
    console.log('Session expires at:', new Date(data.session?.expires_at! * 1000).toISOString());
    
    // Verify cookies are being set by logging cookie headers
    const cookies = res.getHeader('set-cookie');
    if (cookies) {
      console.log('Setting cookies:', Array.isArray(cookies) ? 
        cookies.map(c => c.split(';')[0]) : 
        cookies.split(';')[0]);
    } else {
      console.warn('No cookies set in response headers');
    }

    // Return success response (user data can be useful for the client)
    return res.status(200).json({
      success: true,
      user: {
        id: data.user.id,
        email: data.user.email,
        // Avoid sending sensitive info like session tokens back in the JSON body
      },
      // Add the site URL to help debug redirection issues
      siteUrl: process.env.NEXT_PUBLIC_SITE_URL || 'not set'
    });
  } catch (error: any) {
    console.error('Login API route error:', error);
    return res.status(500).json({ error: error.message || 'Internal server error during login' });
  }
} 