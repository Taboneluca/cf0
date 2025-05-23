"use client"

import { useEffect, useRef, useState } from "react"
import { Loader2, Sparkles, Shuffle, Cpu, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"

type StepEvent =
  | { role: "toolCall"; name: string; args: unknown }
  | { role: "toolResult"; name: string; result: unknown }
  | { role: "assistant" | "user"; content: string }
  | { role: "usage"; prompt_tokens: number; completion_tokens: number }

export default function DebugPanel({ wid }: { wid: string }) {
  const [events, setEvents] = useState<StepEvent[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const url = `${process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/^http/, "ws")}/chat/step?wid=${wid}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onmessage = (e) => {
      const evt: StepEvent = JSON.parse(e.data)
      setEvents(prev => [...prev, evt])
    }
    ws.onclose = () => setConnected(false)

    return () => ws.close()
  }, [wid])

  return (
    <div className="flex flex-col h-full border-l border-gray-200 w-[24rem]">
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <span className="font-medium text-sm">Debug Timeline</span>
        <Button size="sm" variant="outline" onClick={() => wsRef.current?.close()} disabled={!connected}>
          {connected ? <XCircle className="w-4 h-4" /> : "Closed"}
        </Button>
      </div>
      <div className="flex-1 overflow-auto space-y-2 p-3">
        {events.map((e, i) => (
          <div key={i} className="flex items-start text-xs gap-2">
            {/* icon per role */}
            {e.role === "toolCall" && <Cpu className="w-4 h-4 text-purple-500" />}
            {e.role === "toolResult" && <Shuffle className="w-4 h-4 text-green-500" />}
            {e.role === "assistant" && <Sparkles className="w-4 h-4 text-blue-500" />}
            {e.role === "user" && <Loader2 className="w-4 h-4 text-gray-500" />}
            {e.role === "usage" && <Loader2 className="w-4 h-4 text-orange-500" />}

            {/* payload */}
            <pre className="whitespace-pre-wrap">{JSON.stringify(e, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  )
} 