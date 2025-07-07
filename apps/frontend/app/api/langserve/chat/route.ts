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
      console.log('[api/langserve/chat] Forwarding to', `${backendBase}/${mode}/stream`)
    }

    const downstreamUrl = `${backendBase.replace(/\/$/, '')}/${mode}/stream`

    // Initiate fetch to backend with identical headers and body
    const backendResp = await fetch(downstreamUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(payload),
      // Ensure no caching
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

    // Debug log the response
    if (process.env.NODE_ENV !== 'production') {
      console.log('[api/langserve/chat] Backend response:', {
        status: backendResp.status,
        headers: Object.fromEntries(backendResp.headers.entries()),
      })
    }

    // Return the backend response directly with proper SSE headers
    return new Response(backendResp.body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    })
  } catch (err: any) {
    console.error('[api/langserve/chat] Proxy error:', err)
    return new Response(JSON.stringify({ error: 'Proxy error', detail: err?.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

// Next.js will automatically return 405 for other methods 