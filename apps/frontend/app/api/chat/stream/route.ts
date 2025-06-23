import { NextRequest } from 'next/server'
import { createSupabaseServerComponentClient } from '@/lib/supabase/server'
import { cookies } from 'next/headers'

export const runtime = 'nodejs'; // Node Serverless Function (60 s)
export const maxDuration = 60;  // Vercel hobby plan limit

// Support both GET and POST for EventSource compatibility
export async function GET(request: NextRequest) {
  return handleStream(request);
}

export async function POST(request: NextRequest) {
  return handleStream(request);
}

async function handleStream(request: NextRequest) {
  try {
    let body: any;
    
    // Handle GET (EventSource) vs POST requests
    if (request.method === 'GET') {
      const url = new URL(request.url);
      body = {
        mode: url.searchParams.get('mode'),
        message: url.searchParams.get('message'),
        wid: url.searchParams.get('wid'),
        sid: url.searchParams.get('sid'),
        contexts: url.searchParams.get('contexts') ? JSON.parse(url.searchParams.get('contexts')!) : [],
        model: url.searchParams.get('model') || undefined
      };
    } else {
      body = await request.json();
    }
    
    const { mode, message, wid, sid, contexts, model } = body;

    // Authenticate the user
    const supabase = createSupabaseServerComponentClient()
    const { data: { session } } = await supabase.auth.getSession()

    if (!session) {
      return new Response('Unauthorized', { status: 401 })
    }

    // Forward the request to the backend API gateway with optimized headers
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://api.cf0.ai'
    const streamUrl = `${backendUrl}/chat/stream`

    const backendResponse = await fetch(streamUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session.access_token}`,
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify({
        mode,
        message,
        wid,
        sid,
        contexts,
        model,
        user_id: session.user.id
      })
    })

    if (!backendResponse.ok) {
      console.error('Backend API error:', backendResponse.status, backendResponse.statusText)
      return new Response(`Backend error: ${backendResponse.statusText}`, { 
        status: backendResponse.status 
      })
    }

    // Stream the response back to the client with optimized headers (2025 best practices)
    const stream = new ReadableStream({
      start(controller) {
        const reader = backendResponse.body?.getReader()
        if (!reader) {
          controller.close()
          return
        }

        // No more ping intervals - they interfere with real content
        // Let the backend handle keep-alive if needed

        const pump = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read()
              if (done) {
                break
              }
              // Pass through data immediately without buffering
              controller.enqueue(value)
            }
          } catch (error) {
            console.error('Stream error:', error)
            controller.error(error)
          } finally {
            controller.close()
          }
        }

        pump()
      }
    })

    // Return the streaming response with 2025 optimized headers
    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Cache-Control',
        'X-Accel-Buffering': 'no', // Nginx optimization
        'Transfer-Encoding': 'chunked' // Ensure chunked transfer
      }
    })

  } catch (error) {
    console.error('Chat stream API error:', error)
    return new Response('Internal Server Error', { status: 500 })
  }
} 