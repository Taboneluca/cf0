import { NextRequest } from 'next/server'
import { createSupabaseServerComponentClient } from '@/lib/supabase/server'
import { cookies } from 'next/headers'

export const runtime = 'nodejs'; // Node Serverless Function (60 s)
export const maxDuration = 60;  // Vercel hobby plan limit
export const dynamic = 'force-dynamic'; // Prevents caching

// Support both GET and POST for maximum compatibility
export async function GET() {
  return new Response(JSON.stringify({ error: 'Deprecated – use /api/langserve/chat' }), { status: 410, headers: { 'Content-Type': 'application/json' } })
}

export async function POST() {
  return new Response(JSON.stringify({ error: 'Deprecated – use /api/langserve/chat' }), { status: 410, headers: { 'Content-Type': 'application/json' } })
}

async function handleStream(request: NextRequest, method: 'GET' | 'POST') {
  try {
    let body: any;
    
    // Handle different request methods
    if (method === 'GET') {
      // EventSource compatibility - get params from URL
      const url = new URL(request.url);
      body = {
        mode: url.searchParams.get('mode') || 'ask',
        message: url.searchParams.get('message') || '',
        wid: url.searchParams.get('wid') || '',
        sid: url.searchParams.get('sid') || '',
        contexts: JSON.parse(url.searchParams.get('contexts') || '[]'),
        model: url.searchParams.get('model') || ''
      };
    } else {
      // POST request - get data from body
      body = await request.json();
    }

    const { mode, message, wid, sid, contexts, model } = body;

    // Validate required parameters
    if (!message || !wid || !sid) {
      return new Response(
        JSON.stringify({ error: 'Missing required parameters: message, wid, sid' }),
        { 
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    // Check authentication
    const supabase = createSupabaseServerComponentClient();
    const { data: { session } } = await supabase.auth.getSession();

    if (!session) {
      return new Response(
        JSON.stringify({ error: 'Unauthorized' }),
        { 
          status: 401,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    console.log(`[stream] Starting ${method} stream for user ${session.user.email}, mode: ${mode}`);

    // Create the SSE response with proper headers
    const stream = new TransformStream();
    const writer = stream.writable.getWriter();
    const encoder = new TextEncoder();

    // Handle client disconnect
    request.signal.addEventListener('abort', () => {
      console.log('[stream] Client disconnected, closing stream');
      try {
        writer.close();
      } catch (e) {
        // Writer might already be closed
        console.log('[stream] Writer already closed');
      }
    });

    // Start streaming in background
    streamToBackend(writer, encoder, body, session, request.signal);

    // Return streaming response with 2025 optimized headers
    return new Response(stream.readable, {
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'Content-Encoding': 'none', // Critical: Prevents gzip compression issues
        'X-Accel-Buffering': 'no', // Nginx optimization for instant streaming
        'Transfer-Encoding': 'chunked', // Enable chunked transfer
        // CORS headers for cross-origin support
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      },
    });

  } catch (error) {
    console.error('[stream] Error in stream handler:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { 
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

async function streamToBackend(
  writer: WritableStreamDefaultWriter,
  encoder: TextEncoder,
  body: any,
  session: any,
  abortSignal: AbortSignal
) {
  try {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://api.cf0.ai';
    
    console.log(`[stream] Connecting to backend: ${backendUrl}/chat/stream`);

    // Make request to Python backend with proper authentication
    const response = await fetch(`${backendUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session.access_token}`,
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify(body),
      signal: abortSignal
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[stream] Backend error: ${response.status} - ${errorText}`);
      
      // Send error event to client
      const errorEvent = `event: error\ndata: ${JSON.stringify({
        error: `Backend error: ${response.status} ${response.statusText}`,
        code: response.status
      })}\n\n`;
      
      writer.write(encoder.encode(errorEvent));
      writer.close();
      return;
    }

    if (!response.body) {
      throw new Error('No response body from backend');
    }

    console.log('[stream] Backend connection successful, starting stream relay');

    // Stream the response from backend to client
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { value, done } = await reader.read();
        
        if (done) {
          console.log('[stream] Backend stream completed');
          break;
        }

        // Decode and relay the chunk
        const chunk = decoder.decode(value, { stream: true });
        
        // Forward the chunk as-is (backend should send proper SSE format)
        writer.write(encoder.encode(chunk));
        
        // Optional: Log chunk for debugging
        if (process.env.NODE_ENV === 'development') {
          const preview = chunk.length > 100 ? chunk.substring(0, 100) + '...' : chunk;
          console.log(`[stream] Relayed chunk: ${preview}`);
        }
      }
    } finally {
      reader.releaseLock();
    }

  } catch (error: any) {
    console.error('[stream] Error in backend streaming:', error);
    
    if (error.name === 'AbortError') {
      console.log('[stream] Stream aborted by client');
      return;
    }

    // Send error event if writer is still available
    try {
      const errorEvent = `event: error\ndata: ${JSON.stringify({
        error: error.message || 'Streaming error',
        code: 'STREAM_ERROR'
      })}\n\n`;
      
      writer.write(encoder.encode(errorEvent));
    } catch (writeError) {
      console.error('[stream] Failed to write error event:', writeError);
    }
  } finally {
    try {
      writer.close();
    } catch (e) {
      // Writer might already be closed
      console.log('[stream] Writer already closed in finally block');
    }
  }
} 