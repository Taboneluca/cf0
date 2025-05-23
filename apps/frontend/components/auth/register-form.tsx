"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { supabase } from "@/lib/supabase/client"

export function RegisterForm() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [fullName, setFullName] = useState("")
  const [inviteCode, setInviteCode] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()
  const searchParams = useSearchParams()

  // Get invite code from URL if available
  useEffect(() => {
    if (searchParams) {
      const code = searchParams.get("code")
      if (code) {
        setInviteCode(code)

        // Fetch email associated with invite code
        const fetchEmailFromInviteCode = async () => {
          const { data, error } = await supabase.from("waitlist").select("email").eq("invite_code", code).single()

          if (data && !error) {
            setEmail(data.email)
          }
        }

        fetchEmailFromInviteCode()
      }
    }
  }, [searchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      // Verify invite code is valid
      const { data: waitlistData, error: waitlistError } = await supabase
        .from("waitlist")
        .select("email, status")
        .eq("invite_code", inviteCode)
        .single()

      if (waitlistError || !waitlistData) {
        setError("Invalid invite code. Please check and try again.")
        setIsLoading(false)
        return
      }

      if (waitlistData.status !== "approved" && waitlistData.status !== "invited") {
        setError("This invite code is no longer valid.")
        setIsLoading(false)
        return
      }

      if (waitlistData.email !== email) {
        setError("This invite code is for a different email address.")
        setIsLoading(false)
        return
      }

      // Check if we already have a session (via invite link)
      const { data: { session } } = await supabase.auth.getSession();
      
      if (session) {
        // User is already authenticated via invite link, just update password
        const { error: updErr } = await supabase.auth.updateUser({ 
          password,
          data: { full_name: fullName }
        });
        
        if (updErr) throw updErr;
      } else {
        // Fall back to regular sign up if no session
        const { error: signUpError } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: {
              full_name: fullName,
            },
          },
        });

        if (signUpError) throw signUpError;
      }

      // Update waitlist status to converted
      await supabase.from("waitlist").update({ status: "converted" }).eq("invite_code", inviteCode);

      router.push("/dashboard");
    } catch (err: any) {
      console.error("Registration error:", err)
      setError(err.message || "An error occurred during registration")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <label htmlFor="invite-code" className="text-sm font-medium leading-none">
          Invite Code
        </label>
        <input
          id="invite-code"
          type="text"
          value={inviteCode}
          onChange={(e) => setInviteCode(e.target.value)}
          placeholder="Enter your invite code"
          required
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>
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
      <div className="space-y-2">
        <label htmlFor="full-name" className="text-sm font-medium leading-none">
          Full Name
        </label>
        <input
          id="full-name"
          type="text"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="John Doe"
          required
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="password" className="text-sm font-medium leading-none">
          Password
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>
      <button
        type="submit"
        disabled={isLoading}
        className="w-full rounded-md bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
      >
        {isLoading ? "Creating account..." : "Create Account"}
      </button>
      {error && <p className="text-sm text-red-500">{error}</p>}
    </form>
  )
} 