import { NextRequest } from 'next/server'

// Helper to pick the backend base URL
function getBackendBaseUrl() {
  // Prefer an explicit environment variable so that production can target Railway
  const fromEnv = process.env.NEXT_PUBLIC_API_URL || process.env.API_URL
  return fromEnv || 'http://localhost:8000'
}

// POST /api/langserve/chat – proxy to the Python API-gateway streaming endpoint
export async function POST(req: NextRequest) {
  try {
    // Read and forward the JSON payload unchanged
    const payload = await req.json()

    // Determine which downstream endpoint to hit
    const mode = payload?.mode === 'analyst' ? 'analyst' : 'ask'
    const downstreamUrl = `${getBackendBaseUrl()}/${mode}/stream`

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
      // @ts-ignore – Next.js 14.2 supports duplex: 'half'
      duplex: 'half',
    })

    // If backend returned non-OK status propagate as JSON
    if (!backendResp.ok) {
      const text = await backendResp.text()
      return new Response(text, {
        status: backendResp.status,
        headers: { 'Content-Type': backendResp.headers.get('content-type') || 'text/plain' },
      })
    }

    // Pipe the SSE stream straight through to the caller
    return new Response(backendResp.body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
        // Required for streaming in Vercel Edge / Node
        'Transfer-Encoding': 'chunked',
      },
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