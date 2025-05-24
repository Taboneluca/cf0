"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Send, Loader2, X, Sparkles, BarChart3, Minimize2, Maximize2, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import Image from "next/image"
import type { Message as MessageType } from "@/types/spreadsheet"
import { chatBackend } from "@/utils/backend"
import { backendSheetToUI, backendSheetToUIMap } from "@/utils/transform"
import { useWorkbook } from "@/context/workbook-context"
import { useModel } from "@/context/ModelContext"
import ModelSelect from "@/components/ui/ModelSelect"
import { useChatStream } from "@/hooks/useChatStream"
import { PendingBar } from "@/components/PendingBar"
import MessageBubble from "@/components/Message"

interface ChatInterfaceProps {
  messages: MessageType[]
  setMessages: React.Dispatch<React.SetStateAction<MessageType[]>>
  mode: "ask" | "analyst"
  setMode: React.Dispatch<React.SetStateAction<"ask" | "analyst">>
  isMinimized: boolean
  toggleMinimize: () => void
  readOnly?: boolean
}

// Define interface for context ranges
interface ContextRange {
  id: string;
  text: string;
  range: string;
}

export default function ChatInterface({
  messages,
  setMessages,
  mode,
  setMode,
  isMinimized,
  toggleMinimize,
  readOnly = false,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("")
  const [waitingForContext, setWaitingForContext] = useState(false)
  const [ctxStart, setCtxStart] = useState<number|null>(null)   // insertion index
  const lastRangeRef = useRef<string>("")                       // for live replace
  const [contexts, setContexts] = useState<ContextRange[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { model, setModel } = useModel()
  const [wb, dispatch] = useWorkbook()
  const { wid, active, range } = wb

  // Use the streamable chat hook
  const { 
    sendMessage, 
    cancelStream, 
    isStreaming, 
    pendingUpdates,
    applyPendingUpdates,
    rejectPendingUpdates
  } = useChatStream(setMessages, mode)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  // Ensure we scroll to bottom when messages change or during streaming
  useEffect(() => {
    scrollToBottom()
  }, [messages])
  
  // Add auto-scroll during streaming with a more frequent check
  useEffect(() => {
    if (isStreaming) {
      const intervalId = setInterval(() => {
        scrollToBottom()
      }, 100) // Check more frequently during streaming
      
      return () => clearInterval(intervalId)
    }
  }, [isStreaming])

  // Effect to handle live updating of range selection for @-context
  useEffect(() => {
    if (!waitingForContext || ctxStart === null || !range) return

    // Build A1 ref (with sheet! prefix if needed)
    const rangeRef =
      range.sheet === active
        ? `${range.anchor}:${range.focus}`
        : `${range.sheet}!${range.anchor}:${range.focus}`

    // Replace old live text
    setInput(prev => {
      const before = prev.slice(0, ctxStart)        // includes the '@' character
      const after = prev.slice(ctxStart + 1 + lastRangeRef.current.length)  // +1 for the @ character
      lastRangeRef.current = rangeRef
      return `${before}${rangeRef}${after}`
    })

    // Keep cursor right after the entire @range
    setTimeout(() => {
      if (textareaRef.current) {
        const newPos = ctxStart + 1 + rangeRef.length  // +1 for the @ character
        textareaRef.current.setSelectionRange(newPos, newPos)
        textareaRef.current.focus()
      }
    }, 0)
  }, [range, waitingForContext, ctxStart, active])

  const finaliseContext = () => {
    if (!waitingForContext || !range || ctxStart === null) return

    const finalRef = lastRangeRef.current          // already inserted
    const ctxId = `ctx_${contexts.length + 1}`
    setContexts(prev => [...prev, { id: ctxId, text: `@${finalRef}`, range: finalRef }])
    setWaitingForContext(false)
    setCtxStart(null)
    lastRangeRef.current = ""
    
    dispatch({ type: "CLEAR_RANGE" })              // remove blue rectangle
  }

  const handleModeChange = (newMode: "ask" | "analyst") => {
    setMode(newMode)
  }

  const handleRemoveContext = (contextId: string) => {
    // Find the context to remove
    const contextToRemove = contexts.find(ctx => ctx.id === contextId);
    if (!contextToRemove) return;
    
    // Remove the context text from the input
    const newInput = input.replace(contextToRemove.text, "").replace(/\s+/g, " ").trim();
    setInput(newInput);
    
    // Remove from contexts array
    setContexts(contexts.filter(ctx => ctx.id !== contextId));
  }

  const handleSendMessage = async () => {
    if (!input.trim()) return

    // Extract the context ranges to send to backend
    const contextRanges = contexts.map(ctx => ctx.range);
    
    // Use our streamable chat hook
    sendMessage(input, contextRanges, model);
    
    // Reset the input and contexts
    setInput("");
    setContexts([]);
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (waitingForContext && e.key === " ") {
      // Finalise current context
      e.preventDefault()
      finaliseContext()
      return
    }
    
    // Check for @ symbol to start context selection
    if (e.key === '@') {
      const pos = textareaRef.current?.selectionStart ?? input.length
      setWaitingForContext(true)
      setCtxStart(pos)  // Store the position of @ character itself
    }
    
    // Send on Enter (without shift)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-blue-50/50 to-white border-l border-blue-200">
      {isMinimized ? (
        <div
          className="h-full flex items-center justify-center cursor-pointer hover:bg-blue-100 transition-colors border-l border-blue-200 bg-gradient-to-b from-blue-50 to-blue-25 group"
          onClick={toggleMinimize}
        >
          <div className="flex flex-col items-center gap-3 px-2">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl flex items-center justify-center shadow-sm group-hover:scale-105 transition-transform">
              <Image src="/logo.png" alt="cf0" width={20} height={20} className="rounded-sm" />
            </div>
            <Maximize2 className="text-blue-600 group-hover:text-blue-700 transition-colors" size={16} />
            <div className="rotate-90 text-blue-600 group-hover:text-blue-700 font-semibold text-xs whitespace-nowrap tracking-wide">
              AI Assistant
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-blue-200 bg-gradient-to-r from-blue-50 to-blue-25">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl flex items-center justify-center shadow-md">
                <Image src="/logo.png" alt="cf0" width={24} height={24} className="rounded-sm" />
              </div>
              <div>
                <h3 className="font-bold text-blue-900 text-sm">AI Assistant</h3>
                <p className="text-xs text-blue-600">Powered by cf0</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleMinimize}
              className="text-blue-400 hover:text-blue-600 hover:bg-blue-100 p-2 rounded-lg transition-colors"
            >
              <Minimize2 size={16} />
            </Button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message, index) => (
              <div key={index}>
                <MessageBubble message={message} />
              </div>
            ))}
            {isStreaming && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 text-blue-700 bg-blue-50 px-4 py-3 rounded-xl border border-blue-200 shadow-sm">
                  <Loader2 className="animate-spin" size={14} />
                  <span className="text-sm font-medium">Thinking...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t border-blue-200 bg-gradient-to-r from-blue-50/30 to-white p-4">
            {/* Mode Selector - Smaller Dropdown */}
            <div className="mb-3">
              <Select value={mode} onValueChange={handleModeChange}>
                <SelectTrigger className="w-32 h-8 border-blue-300 text-blue-700 bg-white hover:bg-blue-50 transition-colors">
                  <div className="flex items-center gap-2">
                    {mode === "ask" ? <Sparkles size={12} /> : <BarChart3 size={12} />}
                    <SelectValue />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ask" className="text-sm">
                    <div className="flex items-center gap-2">
                      <Sparkles size={12} />
                      Ask
                    </div>
                  </SelectItem>
                  {!readOnly && (
                    <SelectItem value="analyst" className="text-sm">
                      <div className="flex items-center gap-2">
                        <BarChart3 size={12} />
                        Analyst
                      </div>
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
            
            {/* PendingBar for showing updates */}
            <PendingBar 
              visible={pendingUpdates.length > 0}
              pendingCount={pendingUpdates.length}
              onApply={applyPendingUpdates}
              onReject={rejectPendingUpdates}
            />
            
            {/* Model selector */}
            <div className="mb-3">
              <ModelSelect value={model} onChange={setModel} disabled={isStreaming} />
            </div>
            
            {/* Context tags */}
            {contexts.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {contexts.map(ctx => (
                  <div key={ctx.id} className="inline-flex items-center bg-blue-100 text-blue-800 text-xs px-3 py-1.5 rounded-full border border-blue-300 shadow-sm">
                    <span className="font-medium">{ctx.text}</span>
                    <button 
                      onClick={() => handleRemoveContext(ctx.id)}
                      className="ml-2 text-blue-600 hover:text-blue-800 transition-colors"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            
            {/* @-context notification */}
            {waitingForContext && (
              <div className="flex items-center gap-2 text-blue-700 bg-blue-50 px-4 py-3 rounded-xl mb-3 border border-blue-200 shadow-sm">
                <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
                <span className="text-sm font-medium">Select cells to add as context...</span>
              </div>
            )}
            
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={`${
                    mode === "ask" || readOnly
                      ? "Ask about your data... (Type @ to select cell range)"
                      : "Tell me what to change in your spreadsheet..."
                  }`}
                  className="resize-none border-blue-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 rounded-xl text-sm p-4 min-h-[48px] pr-14 bg-white shadow-sm font-['Inter',_system-ui,_sans-serif] placeholder:text-blue-400"
                  rows={2}
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={isStreaming || !input.trim()}
                  className="absolute right-2 bottom-2 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white transition-all h-10 w-10 p-0 rounded-lg shadow-md hover:shadow-lg transform hover:scale-105"
                >
                  {isStreaming ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
} 