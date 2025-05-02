"use client"

import type React from "react"

import { useState } from "react"
import { supabase } from "@/lib/supabase/client"

export function WaitlistStatusForm() {
  const [email, setEmail] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)
    setStatus(null)

    try {
      const { data, error: fetchError } = await supabase
        .from("waitlist")
        .select("status")
        .eq("email", email)
        .maybeSingle()

      if (fetchError && fetchError.code !== 'PGRST116') {
        throw fetchError
      }

      if (!data) {
        setError("Email not found on waitlist. Please join the waitlist first.")
        return
      }

      if (data) {
        if (data.status === "pending") {
          setStatus("Your application is still pending. We'll notify you when you've been approved.")
        } else if (data.status === "approved") {
          setStatus("You've been approved! You should receive an email invitation soon.")
        } else if (data.status === "invited") {
          setStatus("You've been invited! Please check your email for the invitation link.")
        } else if (data.status === "converted") {
          setStatus("You already have an account. Please sign in.")
        }
      }
    } catch (err) {
      console.error("Error checking waitlist status:", err)
      setError("An error occurred. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="email" className="text-sm font-medium leading-none">
          Email
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="name@example.com"
          required
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>
      <button
        type="submit"
        disabled={isLoading}
        className="w-full rounded-md bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
      >
        {isLoading ? "Checking..." : "Check Status"}
      </button>
      {status && <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-600">{status}</div>}
      {error && <p className="text-sm text-red-500">{error}</p>}
    </form>
  )
}
