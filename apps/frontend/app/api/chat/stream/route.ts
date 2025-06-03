import { NextRequest } from 'next/server'
import { createSupabaseServerComponentClient } from '@/lib/supabase/server'
import { cookies } from 'next/headers'

export const runtime = 'nodejs'; // Node Serverless Function (300 s)
export const maxDuration = 60;  // Vercel hobby plan limit

export async function POST(request: NextRequest) {
  try {
    // Get request body
    const body = await request.json()
    const { mode, message, wid, sid, contexts, model } = body

    // Authenticate the user
    const supabase = createSupabaseServerComponentClient()
    const { data: { session } } = await supabase.auth.getSession()

    if (!session) {
      return new Response('Unauthorized', { status: 401 })
    }

    // Forward the request to the backend API gateway
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://api.cf0.ai'
    const streamUrl = `${backendUrl}/chat/stream`

    const backendResponse = await fetch(streamUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session.access_token}`,
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

    // Stream the response back to the client
    const stream = new ReadableStream({
      start(controller) {
        const reader = backendResponse.body?.getReader()
        if (!reader) {
          controller.close()
          return
        }

        const pump = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read()
              if (done) {
                controller.close()
                break
              }
              controller.enqueue(value)
            }
          } catch (error) {
            console.error('Stream error:', error)
            controller.error(error)
          }
        }

        pump()
      }
    })

    // Return the streaming response
    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      }
    })

  } catch (error) {
    console.error('Chat stream API error:', error)
    return new Response('Internal Server Error', { status: 500 })
  }
} 