"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Send, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import type { Message } from "@/types/spreadsheet"
import { chatBackend } from "@/utils/backend"
import { backendSheetToUI, backendSheetToUIMap } from "@/utils/transform"
import { useWorkbook } from "@/context/workbook-context"

interface ChatInterfaceProps {
  messages: Message[]
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  mode: "ask" | "analyst"
  setMode: React.Dispatch<React.SetStateAction<"ask" | "analyst">>
  isMinimized: boolean
  toggleMinimize: () => void
  readOnly?: boolean
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
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [wb, dispatch] = useWorkbook()
  const { wid, active } = wb

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleModeChange = (newMode: "ask" | "analyst") => {
    setMode(newMode)
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
      // Send the chat request with workbook/sheet ID
      const response = await chatBackend(mode, input, wid, active)
      
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

  const handleKeyDown = (e: React.KeyboardEvent) => {
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
            {messages.map((message, index) => (
              <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                {message.role === "user" ? (
                  <div className="max-w-[90%] p-2 rounded-lg bg-blue-500 text-white text-xs">{message.content}</div>
                ) : message.role === "system" ? (
                  <div className="max-w-[90%] text-gray-600 text-xs italic">{message.content}</div>
                ) : (
                  <div className="max-w-[90%] text-gray-700 text-xs">{message.content}</div>
                )}
              </div>
            ))}
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
            <div className="flex gap-1">
              <Textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`${
                  mode === "ask" || readOnly
                    ? "Ask about your data..."
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
