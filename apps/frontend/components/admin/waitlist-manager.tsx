"use client"

import { useState, useEffect } from "react"
import { supabase } from "@/lib/supabase/client"

export function WaitlistManager() {
  const [waitlistEntries, setWaitlistEntries] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [invitingEmail, setInvitingEmail] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Load waitlist data
  useEffect(() => {
    async function loadWaitlist() {
      try {
        const { data, error } = await supabase
          .from("waitlist")
          .select("*")
          .order("created_at", { ascending: false })
        
        if (error) throw error
        setWaitlistEntries(data || [])
      } catch (err: any) {
        console.error("Error loading waitlist:", err)
        setError("Failed to load waitlist data")
      } finally {
        setIsLoading(false)
      }
    }

    loadWaitlist()
  }, [])

  // Invite a user
  const handleInvite = async (email: string) => {
    setInvitingEmail(email)
    setError(null)
    setSuccessMessage(null)
    
    try {
      const response = await fetch("/api/invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      
      const result = await response.json()
      
      if (!response.ok) {
        throw new Error(result.error || "Failed to invite user")
      }
      
      // Update local state with the server-returned data
      setWaitlistEntries(prev => 
        prev.map(entry => 
          entry.email === email 
            ? { ...entry, ...result.data, status: "invited" } 
            : entry
        )
      )
      
      setSuccessMessage(`Successfully invited ${email}`)
    } catch (err: any) {
      console.error("Error inviting user:", err)
      setError(err.message || "An error occurred while inviting the user")
    } finally {
      setInvitingEmail(null)
    }
  }

  if (isLoading) {
    return <div className="text-center py-8">Loading waitlist data...</div>
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Waitlist Manager</h2>
      
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md">
          {error}
        </div>
      )}
      
      {successMessage && (
        <div className="bg-green-50 border border-green-200 text-green-700 p-4 rounded-md">
          {successMessage}
        </div>
      )}
      
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="text-left p-2 border">Email</th>
              <th className="text-left p-2 border">Status</th>
              <th className="text-left p-2 border">Created At</th>
              <th className="text-left p-2 border">Invited At</th>
              <th className="text-left p-2 border">Actions</th>
            </tr>
          </thead>
          <tbody>
            {waitlistEntries.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center p-4 border">
                  No waitlist entries found
                </td>
              </tr>
            ) : (
              waitlistEntries.map((entry) => (
                <tr key={entry.id} className="border-t">
                  <td className="p-2 border">{entry.email}</td>
                  <td className="p-2 border">
                    <span className={`px-2 py-1 rounded-full text-xs ${
                      entry.status === "pending" ? "bg-yellow-100 text-yellow-800" :
                      entry.status === "approved" ? "bg-blue-100 text-blue-800" :
                      entry.status === "invited" ? "bg-green-100 text-green-800" :
                      entry.status === "converted" ? "bg-purple-100 text-purple-800" :
                      "bg-gray-100"
                    }`}>
                      {entry.status}
                    </span>
                  </td>
                  <td className="p-2 border">{new Date(entry.created_at).toLocaleDateString()}</td>
                  <td className="p-2 border">
                    {entry.invited_at ? new Date(entry.invited_at).toLocaleDateString() : "-"}
                  </td>
                  <td className="p-2 border">
                    {entry.status === "pending" && (
                      <button
                        onClick={() => handleInvite(entry.email)}
                        disabled={invitingEmail === entry.email}
                        className="bg-blue-500 hover:bg-blue-600 text-white py-1 px-3 rounded text-sm disabled:opacity-50"
                      >
                        {invitingEmail === entry.email ? "Inviting..." : "Invite"}
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
} 