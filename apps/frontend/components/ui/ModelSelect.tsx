"use client"

import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"

/** Canonical list, keep in sync with backend llm.PROVIDERS map */
export const MODELS = [
  { label: "GPT-4o", value: "openai:gpt-4o" },
  { label: "GPT-4o mini", value: "openai:gpt-4o-mini" },
  { label: "GPT-o3", value: "openai:gpt-o3" },
  { label: "GPT-o4 mini", value: "openai:gpt-o4-mini" },
  { label: "Claude 3.5 Sonnet", value: "anthropic:claude-3-5-sonnet-latest" },
  { label: "Claude 3.7 Sonnet", value: "anthropic:claude-3-7-sonnet-latest" },
  { label: "LLAMA 3.3 70B", value: "groq:llama-3.3-70b-versatile" },
  { label: "LLAMA 3.1 8B", value: "groq:llama-3.1-8b-instant" },
]

interface ModelSelectProps {
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

export default function ModelSelect({ value, onChange, disabled }: ModelSelectProps) {
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger className="h-8 w-[11rem] border-gray-300 text-xs">
        <SelectValue placeholder="Select model" />
      </SelectTrigger>
      <SelectContent>
        {MODELS.map(m => (
          <SelectItem key={m.value} value={m.value} className="text-xs">
            {m.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
} 