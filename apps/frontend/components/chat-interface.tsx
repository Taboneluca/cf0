"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Send, Loader2, X, Sparkles, BarChart3, Minimize2, Maximize2, ChevronDown, Save } from "lucide-react"
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
  workbookControls?: {
    onSave: () => void
    isSaving: boolean
    lastSaved: Date | null
  }
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
  workbookControls,
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
    <div className="flex flex-col h-full bg-[#1a1a1a] border-l border-gray-800">
      {isMinimized ? (
        <div
          className="h-full flex items-center justify-center cursor-pointer hover:bg-gray-900 transition-colors border-l border-gray-800 bg-[#1a1a1a] group"
          onClick={toggleMinimize}
        >
          <div className="flex flex-col items-center gap-3 px-2">
            <div className="w-6 h-6 rounded flex items-center justify-center">
              <Image src="/transparent_image_v2.png" alt="cf0" width={16} height={16} className="rounded-sm" />
            </div>
            <Maximize2 className="text-gray-400 group-hover:text-gray-300 transition-colors" size={14} />
            <div className="rotate-90 text-gray-400 group-hover:text-gray-300 font-mono text-xs whitespace-nowrap tracking-wide">
              cf0
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800 bg-[#1a1a1a]">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded flex items-center justify-center">
                <Image src="/transparent_image_v2.png" alt="cf0" width={14} height={14} className="rounded-sm" />
              </div>
              <span className="font-mono text-gray-300 text-sm">cf0</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleMinimize}
              className="text-gray-500 hover:text-gray-300 hover:bg-gray-800 p-1 h-6 w-6 rounded transition-colors"
            >
              <Minimize2 size={12} />
            </Button>
          </div>

          {/* Workbook Controls - only show if provided */}
          {workbookControls && (
            <div className="px-3 py-2 border-b border-gray-800 bg-[#1a1a1a] space-y-2">
              <button
                onClick={workbookControls.onSave}
                disabled={workbookControls.isSaving}
                className="flex items-center gap-2 rounded-md bg-blue-600 hover:bg-blue-700 px-3 py-1.5 text-xs text-white disabled:opacity-50 w-full justify-center transition-colors"
              >
                <Save size={12} />
                {workbookControls.isSaving ? "Saving..." : "Save"}
              </button>
              {workbookControls.lastSaved && (
                <div className="text-xs text-gray-400 text-center">
                  Last saved: {workbookControls.lastSaved.toLocaleTimeString()}
                </div>
              )}
            </div>
          )}

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-[#1a1a1a]">
            {messages.map((message, index) => (
              <div key={index}>
                <MessageBubble message={message} />
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t border-gray-800 bg-[#1a1a1a] p-3 space-y-2">
            {/* Mode and Model Selectors - Much smaller and compact */}
            <div className="flex items-center gap-1">
              <Select value={mode} onValueChange={handleModeChange}>
                <SelectTrigger className="w-auto min-w-[60px] h-4 border-gray-700 text-gray-300 bg-gray-800 hover:bg-gray-700 transition-colors text-xs">
                  <SelectValue>
                    {mode === "ask" ? "Ask" : "Analyst"}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent className="bg-gray-800 border-gray-700">
                  <SelectItem value="ask" className="text-xs text-gray-300 hover:bg-gray-700">
                    Ask
                  </SelectItem>
                  {!readOnly && (
                    <SelectItem value="analyst" className="text-xs text-gray-300 hover:bg-gray-700">
                      Analyst
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
              
              <div className="text-xs text-gray-500">|</div>
              
              <div className="flex-1 min-w-0">
                <ModelSelect value={model} onChange={setModel} disabled={isStreaming} />
              </div>
            </div>
            
            {/* PendingBar for showing updates */}
            <PendingBar 
              visible={pendingUpdates.length > 0}
              pendingCount={pendingUpdates.length}
              onApply={applyPendingUpdates}
              onReject={rejectPendingUpdates}
            />
            
            {/* Context tags */}
            {contexts.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {contexts.map(ctx => (
                  <div key={ctx.id} className="inline-flex items-center bg-gray-800 text-gray-300 text-xs px-2 py-1 rounded border border-gray-700">
                    <span className="font-mono">{ctx.text}</span>
                    <button 
                      onClick={() => handleRemoveContext(ctx.id)}
                      className="ml-1 text-gray-500 hover:text-gray-300 transition-colors"
                    >
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            
            {/* @-context notification */}
            {waitingForContext && (
              <div className="flex items-center gap-2 text-gray-400 bg-gray-800 px-3 py-2 rounded text-xs border border-gray-700">
                <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-pulse" />
                <span className="font-mono">Select cells to add as context...</span>
              </div>
            )}
            
            <div className="flex gap-2">
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
                  className="resize-none border-gray-700 focus:ring-1 focus:ring-gray-600 focus:border-gray-600 rounded text-xs p-2 min-h-[24px] pr-8 bg-gray-800 text-gray-300 font-mono placeholder:text-gray-500"
                  rows={1}
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={isStreaming || !input.trim()}
                  className="absolute right-1 bottom-1 bg-gray-700 hover:bg-gray-600 text-gray-300 transition-all h-5 w-5 p-0 rounded"
                >
                  {isStreaming ? <Loader2 className="animate-spin" size={10} /> : <Send size={10} />}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
} 