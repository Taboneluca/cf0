"use client"

import Link from "next/link"

import type React from "react"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { supabase } from "@/lib/supabase/client"

export function LoginForm() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()
  const searchParams = useSearchParams()
  
  // Check if we were redirected from a protected page
  useEffect(() => {
    const from = searchParams?.get('from')
    if (from) {
      setError(`You need to be logged in to access ${from}`)
    }
  }, [searchParams])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      console.log("Attempting login with:", email)
      
      // First verify if we have a session already to avoid unnecessary logins
      const { data: existingSession } = await supabase.auth.getSession()
      if (existingSession.session) {
        console.log("Already have a valid session, navigating to dashboard")
        router.push('/dashboard')
        return
      }
      
      // Use our server-side login API endpoint
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
        // Important: Include credentials to ensure cookies are sent
        credentials: 'include',
      })
      
      // Log the response status and headers for debugging
      console.log("Login response status:", response.status)
      
      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to sign in')
      }
      
      console.log("Login successful, navigating to dashboard")
      
      // Check if cookies were set properly
      document.cookie.split(';').forEach(cookie => {
        const trimmed = cookie.trim()
        if (trimmed.startsWith('sb-') || trimmed.startsWith('supabase-')) {
          console.log("Auth cookie detected:", trimmed.split('=')[0])
        }
      })
      
      // After successful login, verify the session with Supabase client
      const { data: sessionData, error: sessionError } = await supabase.auth.getSession()
      
      if (sessionError || !sessionData.session) {
        console.error("Session verification failed after login:", sessionError?.message || "No session found")
        
        // Try direct sign in with the Supabase client as fallback
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email,
          password
        })
        
        if (signInError) {
          console.error("Fallback sign-in failed:", signInError.message)
        } else {
          console.log("Fallback sign-in successful")
        }
      } else {
        console.log("Session verified, expires:", 
          sessionData.session.expires_at 
            ? new Date(sessionData.session.expires_at * 1000).toISOString()
            : 'no expiration date'
        )
      }
      
      // Refresh all route caches
      router.refresh()
      
      // Get the redirect destination, defaulting to dashboard
      const destination = searchParams?.get('from') || '/dashboard'
      router.push(destination)
    } catch (err: any) {
      console.error("Login error:", err)
      setError(err.message || "An error occurred during login")
    } finally {
      setIsLoading(false)
    }
  }

  const handleSignInWithMagicLink = async (e: React.MouseEvent) => {
    e.preventDefault()
    if (!email) {
      setError("Please enter your email address")
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/auth/magic-link', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
        credentials: 'include',
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to send magic link')
      }

      setEmail("")
      alert("Check your email for the login link!")
    } catch (err: any) {
      console.error("Magic link error:", err)
      setError(err.message || "An error occurred sending the magic link")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-4">
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
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label htmlFor="password" className="text-sm font-medium leading-none">
              Password
            </label>
            <Link href="/reset-password" className="text-sm text-blue-500 hover:text-blue-600">
              Forgot password?
            </Link>
          </div>
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
          {isLoading ? "Signing in..." : "Sign In"}
        </button>
      </form>
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-background px-2 text-muted-foreground">Or continue with</span>
        </div>
      </div>
      <button
        onClick={handleSignInWithMagicLink}
        disabled={isLoading}
        className="w-full rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
      >
        {isLoading ? "Sending..." : "Magic Link"}
      </button>
      {error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  )
}
