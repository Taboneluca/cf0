import { NextRequest } from 'next/server'
import { createSupabaseServerComponentClient } from '@/lib/supabase/server'

export const runtime = 'nodejs'
export const maxDuration = 60
export const dynamic = 'force-dynamic'

export async function POST(request: NextRequest) {
  return handle(request, 'POST')
}
export async function GET(request: NextRequest) {
  return handle(request, 'GET')
}

async function handle(req: NextRequest, method: 'GET' | 'POST') {
  // authenticate
  const supabase = createSupabaseServerComponentClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) {
    return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401, headers: { 'Content-Type': 'application/json' } })
  }

  // parse body or query
  let body: any
  if (method === 'GET') {
    const url = new URL(req.url)
    body = Object.fromEntries(url.searchParams.entries())
  } else {
    body = await req.json()
  }

  // Sanitize request payload to prevent null/undefined values
  const sanitizePayload = (payload: any) => {
    const sanitized: any = {}
    
    // Ensure required fields are present and properly typed
    sanitized.mode = payload.mode || 'ask'
    sanitized.message = payload.message || ''
    sanitized.wid = payload.wid || 'default'
    sanitized.sid = payload.sid || 'Sheet1'
    
    // Ensure contexts is always an array (never null or undefined)
    sanitized.contexts = Array.isArray(payload.contexts) ? payload.contexts : []
    
    // Only include model if it's a non-empty string
    if (typeof payload.model === 'string' && payload.model.trim()) {
      sanitized.model = payload.model.trim()
    }
    
    return sanitized
  }

  const sanitizedBody = sanitizePayload(body)
  
  // Log the sanitized payload for debugging 422 errors
  if (process.env.NODE_ENV === 'development') {
    console.log('🔍 LangServe request payload:', JSON.stringify(sanitizedBody, null, 2))
  }

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://api.cf0.ai'
  const mode = sanitizedBody.mode
  const targetPath = mode === 'analyst' ? '/analyst/stream' : '/ask/stream'

  // forward to backend langserve endpoint
  const resp = await fetch(`${backendUrl}${targetPath}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
      'Cache-Control': 'no-cache',
    },
    body: JSON.stringify(sanitizedBody),
    signal: req.signal,
  })

  if (!resp.body) {
    return new Response(JSON.stringify({ error: 'No response body' }), { status: 500 })
  }

  // create transform stream to pipe directly
  const { readable, writable } = new TransformStream()
  resp.body.pipeTo(writable)
  return new Response(readable, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    }
  })
} 