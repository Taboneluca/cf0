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
    
    // Set stronger cache control to prevent caching auth responses
    res.setHeader('Cache-Control', 'private, no-cache, no-store, must-revalidate, max-age=0');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
    
    // Verify cookies are being set by logging cookie headers
    const cookies = res.getHeader('set-cookie');
    if (cookies) {
      console.log('Setting cookies:', Array.isArray(cookies) ? 
        cookies.map(c => c.split(';')[0]) : 
        (typeof cookies === 'string' ? cookies.split(';')[0] : cookies));
      
      // Make sure our session cookie has secure attributes
      if (Array.isArray(cookies)) {
        const authCookie = cookies.find(c => c.includes('sb-'));
        if (authCookie) {
          console.log('Auth cookie attributes:', authCookie.split(';').map(attr => attr.trim()).join(', '));
        }
      } else if (typeof cookies === 'string' && cookies.includes('sb-')) {
        console.log('Auth cookie attributes:', cookies.split(';').map(attr => attr.trim()).join(', '));
      }
    } else {
      console.warn('No cookies set in response headers');
    }

    // Return success response with minimal data
    return res.status(200).json({
      success: true,
      user: {
        id: data.user.id,
        email: data.user.email,
      },
      // Include session info for debugging but not the actual token
      session: {
        expires_at: data.session?.expires_at,
      },
      siteUrl: process.env.NEXT_PUBLIC_SITE_URL || 'not set'
    });
  } catch (error: any) {
    console.error('Login API route error:', error);
    return res.status(500).json({ error: error.message || 'Internal server error during login' });
  }
} 