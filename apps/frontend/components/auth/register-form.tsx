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
          try {
            const { data, error } = await supabase
              .from("waitlist")
              .select("email")
              .eq("invite_code", code)
              .single()

            if (data && !error) {
              setEmail(data.email)
            } else {
              console.error("Error fetching email from invite code:", error)
            }
          } catch (err) {
            console.error("Failed to fetch email:", err)
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

    // Basic validation
    if (!email || !password || !fullName || !inviteCode) {
      setError("All fields are required")
      setIsLoading(false)
      return
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters")
      setIsLoading(false)
      return
    }

    try {
      console.log("Starting registration process for:", email)

      // First verify invite code is valid via direct query
      const { data: waitlistData, error: waitlistError } = await supabase
        .from("waitlist")
        .select("email, status")
        .eq("invite_code", inviteCode)
        .single()

      if (waitlistError || !waitlistData) {
        console.error("Invite code verification failed:", waitlistError)
        setError("Invalid invite code. Please check and try again.")
        setIsLoading(false)
        return
      }

      if (waitlistData.status !== "invited") {
        setError("This invite code is no longer valid or has already been used.")
        setIsLoading(false)
        return
      }

      if (waitlistData.email !== email) {
        setError("This invite code is for a different email address.")
        setIsLoading(false)
        return
      }

      console.log("Invite code verified, proceeding with signup")

      // Check if we already have a session (via invite link)
      const { data: { session } } = await supabase.auth.getSession()
      
      if (session && session.user.email === email) {
        console.log("User already has session, updating password")
        // User is already authenticated via invite link, just update password and profile
        const { error: updateError } = await supabase.auth.updateUser({ 
          password,
          data: { full_name: fullName }
        })
        
        if (updateError) {
          console.error("Error updating user:", updateError)
          throw updateError
        }
      } else {
        console.log("Creating new user account")
        // Create new account
        const { data: signUpData, error: signUpError } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: {
              full_name: fullName,
            },
          },
        })

        if (signUpError) {
          console.error("Signup error:", signUpError)
          throw signUpError
        }

        if (!signUpData.user) {
          throw new Error("Failed to create user account")
        }

        console.log("User account created successfully")
      }

      // Now update waitlist status via secure API endpoint (not direct client update)
      console.log("Updating waitlist status via API")
      const updateResponse = await fetch('/api/auth/complete-registration', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          inviteCode: inviteCode,
          email: email 
        }),
        credentials: 'include',
      })

      if (!updateResponse.ok) {
        const errorData = await updateResponse.json()
        console.error("Failed to update waitlist status:", errorData)
        // Don't fail registration for this - user is created but status might not update
        console.warn("Registration succeeded but waitlist status update failed")
      } else {
        console.log("Waitlist status updated successfully")
      }

      console.log("Registration complete, redirecting to dashboard")
      router.push("/dashboard")
    } catch (err: any) {
      console.error("Registration error:", err)
      setError(err.message || "An error occurred during registration. Please try again.")
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
          placeholder="Minimum 6 characters"
          required
          minLength={6}
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
      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}
    </form>
  )
} 