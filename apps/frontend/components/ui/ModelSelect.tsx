"use client"

import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select"

/** Canonical list, keep in sync with backend llm.PROVIDERS map */
export const MODELS = [
  { label: "GPT-4o mini", value: "openai:gpt-4o-mini" },
  { label: "Claude 3 Haiku", value: "anthropic:claude-3-haiku" },
  { label: "LLAMA 3 (Groq)", value: "groq:llama3-70b" },
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