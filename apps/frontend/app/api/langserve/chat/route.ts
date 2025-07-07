import { NextRequest } from 'next/server'

// Helper to pick the backend base URL
function getBackendBaseUrl() {
  // Prefer newer NEXT_PUBLIC_BACKEND_URL but fall back to older names for back-compat
  const fromEnv =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.API_URL

  return fromEnv || 'http://localhost:8000'
}

// POST /api/langserve/chat – proxy to the Python API-gateway streaming endpoint
export async function POST(req: NextRequest) {
  try {
    // Read and forward the JSON payload unchanged
    const payload = await req.json()

    // Determine which downstream endpoint to hit
    const mode = payload?.mode === 'analyst' ? 'analyst' : 'ask'
    const backendBase = getBackendBaseUrl()
    if (process.env.NODE_ENV !== 'production') {
      console.log('[api/langserve/chat] Using backend', backendBase)
    }

    const downstreamUrl = `${backendBase.replace(/\/$/, '')}/${mode}/stream`

    // Initiate fetch to backend with identical headers and body
    const backendResp = await fetch(downstreamUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // The backend returns SSE, so we explicitly request that
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(payload),
      // We need the Response body as a stream
      cache: 'no-store',
    })

    // If backend returned non-OK status propagate as JSON
    if (!backendResp.ok) {
      const text = await backendResp.text()
      return new Response(text, {
        status: backendResp.status,
        headers: { 'Content-Type': backendResp.headers.get('content-type') || 'text/plain' },
      })
    }

    // For streaming responses, we need to ensure proper headers and no buffering
    const headers = new Headers({
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      // Disable compression for SSE
      'Content-Encoding': 'none',
      // Disable buffering
      'X-Accel-Buffering': 'no',
    })

    // Create a TransformStream to ensure proper streaming
    const stream = new TransformStream()
    const writer = stream.writable.getWriter()
    const encoder = new TextEncoder()

    // Start piping the backend response to our stream
    if (backendResp.body) {
      const reader = backendResp.body.getReader()
      
      // Read and forward chunks
      ;(async () => {
        try {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            
            // Forward the chunk directly
            await writer.write(value)
          }
        } catch (error) {
          console.error('[api/langserve/chat] Stream error:', error)
        } finally {
          await writer.close()
        }
      })()
    }

    // Return the streaming response
    return new Response(stream.readable, {
      status: 200,
      headers,
    })
  } catch (err: any) {
    console.error('[api/langserve/chat] Proxy error', err)
    return new Response(JSON.stringify({ error: 'Proxy error', detail: err?.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

// Next.js will automatically return 405 for other methods 