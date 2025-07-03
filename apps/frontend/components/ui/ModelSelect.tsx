"use client"

import { useEffect, useState } from 'react'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"
import useSupabaseSession from "@/hooks/useSupabaseSession"

// Types for models from API
interface Model {
  label: string
  value: string
  provider: string
  tool_calls: boolean
}

// Default models in case API fails
const DEFAULT_MODELS: Model[] = [
  { label: "gpt-4o", value: "openai:gpt-4o", provider: "openai", tool_calls: true },
  { label: "claude-3.7-Sonnet", value: "anthropic:claude-3-7-sonnet", provider: "anthropic", tool_calls: true },
  { label: "Llama-3.3-70B", value: "groq:llama-3-3-70b", provider: "groq", tool_calls: true },
]

interface ModelSelectProps {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

export default function ModelSelect({ value, onChange, disabled }: ModelSelectProps) {
  // Use client-side state to prevent hydration errors
  const [clientValue, setClientValue] = useState<string | null>(null)
  const [models, setModels] = useState<Model[]>(DEFAULT_MODELS)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { session } = useSupabaseSession()
  
  // Fetch models from API
  useEffect(() => {
    const fetchModels = async () => {
      try {
        setLoading(true)
        const response = await fetch("https://api.cf0.ai/models")
        
        if (!response.ok) {
          throw new Error(`API error: ${response.status}`)
        }
        
        const data: Model[] = await response.json()
        if (Array.isArray(data) && data.length > 0) {
          setModels(data)
          // If current value is not in new models list, select first one
          if (data.findIndex(m => m.value === value) === -1) {
            onChange(data[0].value)
          }
        }
      } catch (err) {
        console.error("Failed to fetch models:", err)
        setError(err instanceof Error ? err.message : "Unknown error")
      } finally {
        setLoading(false)
      }
    }
    
    fetchModels()
  }, [])
  
  // Only set the client value once mounted and we have the session (client-side)
  useEffect(() => {
    setClientValue(value)
  }, [value, session])
  
  // Function to set model and also persist to Supabase if possible
  const handleModelChange = async (newModel: string) => {
    console.log('Model changed from', clientValue, 'to', newModel);
    onChange(newModel);
    
    // Optional: save to user's profile in Supabase
    try {
      // This would be the place to save the user preference to a backend
      // const { data, error } = await supabase.from('profiles').update({ default_model: newModel })
    } catch (error) {
      console.error('Error saving model preference:', error)
    }
  }

  // Don't render anything during SSR to prevent hydration mismatch
  if (clientValue === null) return null

  return (
    <Select value={clientValue} onValueChange={handleModelChange} disabled={disabled || loading}>
      <SelectTrigger className="h-4 w-full border-gray-700 text-gray-300 bg-gray-800 hover:bg-gray-700 transition-colors text-xs font-mono">
        <SelectValue placeholder={loading ? "Loading..." : "Select model"} />
      </SelectTrigger>
      <SelectContent className="bg-gray-800 border-gray-700">
        {models.map(m => (
          <SelectItem key={m.value} value={m.value} className="text-xs text-gray-300 hover:bg-gray-700 font-mono">
            {m.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
} 