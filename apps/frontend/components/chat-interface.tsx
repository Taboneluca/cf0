"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Send, Loader2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import type { Message } from "@/types/spreadsheet"
import { chatBackend } from "@/utils/backend"
import { backendSheetToUI, backendSheetToUIMap } from "@/utils/transform"
import { useWorkbook } from "@/context/workbook-context"
import { useModel } from "@/context/ModelContext"
import ModelSelect from "@/components/ui/ModelSelect"

interface ChatInterfaceProps {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
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
  const [isLoading, setIsLoading] = useState(false)
  const [waitingForContext, setWaitingForContext] = useState(false)
  const [ctxStart, setCtxStart] = useState<number|null>(null)   // insertion index
  const lastRangeRef = useRef<string>("")                       // for live replace
  const [contexts, setContexts] = useState<ContextRange[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const { model, setModel } = useModel()
  const [wb, dispatch] = useWorkbook()
  const { wid, active, range } = wb

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

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

    const userMessage: Message = {
      role: "user",
      content: input,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput("")
    setIsLoading(true)
    
    console.log(`💬 Sending chat message with mode=${mode}, wid=${wid}, sheet=${active}`)

    try {
      // Extract the context ranges to send to backend
      const contextRanges = contexts.map(ctx => ctx.range);
      
      // Send the chat request with workbook/sheet ID and contexts
      const response = await chatBackend(mode, input, wid, active, contextRanges, model)
      
      // Reset contexts after sending
      setContexts([]);
      
      console.log(`📊 Chat response received:`, {
        replyLength: response?.reply?.length,
        hasSheet: !!response?.sheet,
        sheetName: response?.sheet?.name,
      })
      
      // Defensive check for required fields
      if (!response) {
        console.error("❌ Empty response from chatBackend")
        throw new Error("Empty response from server")
      }
      
      if (!response.reply) {
        console.error("❌ Missing reply in response:", response)
        throw new Error("Missing reply in server response")
      }
      
      if (!response.sheet) {
        console.error("❌ Missing sheet data in response:", {
          hasReply: !!response.reply,
          hasSheet: !!response.sheet,
        })
        throw new Error("Missing sheet data in server response")
      }
      
      // Update the active sheet directly from the backend response
      console.log(`📝 Updating sheet ${active} from response`)
      
      try {
        const uiSheet = backendSheetToUI(response.sheet)
        dispatch({
          type: "UPDATE_SHEET", 
          sid: active, 
          data: uiSheet
        })
        console.log(`✅ Sheet ${active} updated successfully`)
      } catch (sheetError: any) {
        console.error("❌ Error updating sheet:", sheetError)
        throw new Error(`Error updating sheet: ${sheetError.message}`)
      }
      
      // Merge all sheets data into the context
      if (response.all_sheets) {
        try {
          console.log(`📊 Merging data for ${Object.keys(response.all_sheets).length} sheets`)
          const uiSheets = backendSheetToUIMap(response.all_sheets)
          dispatch({
            type: "MERGE_SHEETS_DATA",
            data: uiSheets
          })
          console.log(`✅ All sheets merged successfully`)
        } catch (sheetsError: any) {
          console.error("❌ Error merging sheets:", sheetsError)
          // Don't throw here - we can continue with the single sheet update
        }
      }

      const assistantMessage: Message = {
        role: "assistant",
        content: response.reply,
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      console.error("❌ Error in handleSendMessage:", error)
      
      // Log more details about the current state
      console.error("Current state:", {
        mode,
        wid,
        active,
        workbookData: !!wb,
        messageCount: messages.length
      })
      
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error while processing your request.",
        },
      ])
    } finally {
      setIsLoading(false)
    }
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
    <div className="flex flex-col h-full bg-white">
      {isMinimized ? (
        <div
          className="h-full flex items-center justify-center cursor-pointer hover:bg-gray-50 transition-colors"
          onClick={toggleMinimize}
        >
          <div className="rotate-90 text-gray-500 whitespace-nowrap writing-mode-vertical-lr">cf0.ai</div>
        </div>
      ) : (
        <div className="flex flex-col h-full">
          <div className="flex-1 overflow-y-auto p-2 space-y-2">
            {messages.map((message, index) => {
              const parts = message.content.split(/(@[\w!:.]+)/g)
              return (
                <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                  {message.role === "user" ? (
                    <div className="max-w-[90%] p-2 rounded-lg bg-blue-500 text-white text-xs">
                      {parts.map((part, i) => 
                        part.match(/^@[\w!:.]+$/) 
                          ? <span key={i} className="font-semibold underline">{part}</span>
                          : <span key={i}>{part}</span>
                      )}
                    </div>
                  ) : message.role === "system" ? (
                    <div className="max-w-[90%] text-gray-600 text-xs italic">{message.content}</div>
                  ) : (
                    <div className="max-w-[90%] text-gray-700 text-xs">
                      {parts.map((part, i) => 
                        part.match(/^@[\w!:.]+$/) 
                          ? <span key={i} className="text-blue-600 font-semibold">{part}</span>
                          : <span key={i}>{part}</span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
            {isLoading && (
              <div className="flex justify-start">
                <div className="text-gray-700">
                  <Loader2 className="animate-spin text-blue-500" size={16} />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="border-t border-gray-200 p-2">
            <div className="mb-2">
              <div className="inline-flex items-center gap-1 bg-gray-800 text-white p-0.5 rounded-md">
                <button
                  onClick={() => handleModeChange("ask")}
                  className={`px-2 py-0.5 text-xs rounded ${
                    mode === "ask" ? "bg-gray-600" : "hover:bg-gray-700"
                  } transition-colors`}
                >
                  Ask
                </button>
                {!readOnly && (
                  <button
                    onClick={() => handleModeChange("analyst")}
                    className={`px-2 py-0.5 text-xs rounded ${
                      mode === "analyst" ? "bg-gray-600" : "hover:bg-gray-700"
                    } transition-colors`}
                  >
                    Analyst
                  </button>
                )}
              </div>
            </div>
            
            {/* Model selector */}
            <div className="mb-2">
              <ModelSelect value={model} onChange={setModel} disabled={isLoading} />
            </div>
            
            {/* Context tags */}
            {contexts.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-2">
                {contexts.map(ctx => (
                  <div key={ctx.id} className="inline-flex items-center bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                    {ctx.text}
                    <button 
                      onClick={() => handleRemoveContext(ctx.id)}
                      className="ml-1 text-blue-600 hover:text-blue-800"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            
            {/* @-context notification */}
            {waitingForContext && (
              <div className="text-xs text-blue-600 mb-1">
                Select cells to add as context...
              </div>
            )}
            
            <div className="flex gap-1">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`${
                  mode === "ask" || readOnly
                    ? "Ask about your data... (Type @ to select cell range as context)"
                    : "Tell me what to change in your spreadsheet..."
                }`}
                className="flex-1 resize-none border-gray-200 focus:ring-blue-500 focus:border-blue-500 text-xs p-1 min-h-[40px]"
                rows={2}
              />
              <Button
                onClick={handleSendMessage}
                disabled={isLoading || !input.trim()}
                className="self-end bg-blue-500 hover:bg-blue-600 transition-colors h-8 w-8 p-0"
              >
                {isLoading ? <Loader2 className="animate-spin" size={14} /> : <Send size={14} />}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
