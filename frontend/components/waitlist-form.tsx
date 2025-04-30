"use client"

import type React from "react"

import { useState } from "react"
import { supabase } from "@/lib/supabase/client"

export function WaitlistForm() {
  const [email, setEmail] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSuccess, setIsSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    setError(null)

    try {
      // Check if email already exists in waitlist
      const { data: existingEntries, error: selectError } = await supabase
        .from("waitlist")
        .select("id, status")
        .eq("email", email)
        .maybeSingle()

      if (selectError && selectError.code !== 'PGRST116') {
        throw selectError
      }

      if (existingEntries) {
        if (existingEntries.status === "pending") {
          setError("This email is already on our waitlist.")
        } else if (existingEntries.status === "approved" || existingEntries.status === "invited") {
          setError("This email has already been approved. Please check your inbox for the invite.")
        } else if (existingEntries.status === "converted") {
          setError("This email is already registered. Please sign in.")
        }
        setIsSubmitting(false)
        return
      }

      // Add email to waitlist
      const { error: insertError } = await supabase.from("waitlist").insert([{ email }])

      if (insertError) throw insertError

      setIsSuccess(true)
    } catch (err) {
      console.error("Error submitting to waitlist:", err)
      setError("An error occurred. Please try again.")
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isSuccess) {
    return (
      <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-600">
        Thanks for joining our waitlist! Our team will review your request and send you an invite when approved.
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-md space-y-2">
      <div className="flex flex-col sm:flex-row gap-2">
        <input
          type="email"
          placeholder="Enter your email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isSubmitting}
          className="inline-flex h-10 items-center justify-center rounded-md bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50"
        >
          {isSubmitting ? "Submitting..." : "Join Waitlist"}
        </button>
      </div>
      {error && <p className="text-sm text-red-500">{error}</p>}
    </form>
  )
}
