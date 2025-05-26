"use client"

import { useState, useEffect } from "react"
import { supabase } from "@/lib/supabase/client"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table"
import { Check, X, RefreshCw, Mail, Trash2 } from "lucide-react"
import type { WaitlistEntry } from "@/types/database"

export function WaitlistManager() {
  const [waitlistEntries, setWaitlistEntries] = useState<WaitlistEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actioningEmail, setActioningEmail] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Load waitlist data
  useEffect(() => {
    loadWaitlist()
  }, [])

  const loadWaitlist = async () => {
    try {
      setIsLoading(true)
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

  // Approve a user
  const handleApprove = async (email: string) => {
    setActioningEmail(email)
    setError(null)
    setSuccessMessage(null)
    
    try {
      const response = await fetch("/api/admin/invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      
      const result = await response.json()
      
      if (!response.ok) {
        throw new Error(result.error || "Failed to invite user")
      }
      
      // Update local state
      setWaitlistEntries(prev => 
        prev.map(entry => 
          entry.email === email 
            ? { ...entry, status: "invited", invited_at: new Date().toISOString() } 
            : entry
        )
      )
      
      setSuccessMessage(`Successfully invited ${email}`)
    } catch (err: any) {
      console.error("Error inviting user:", err)
      setError(err.message || "An error occurred while inviting the user")
    } finally {
      setActioningEmail(null)
    }
  }

  // Reject a user
  const handleReject = async (email: string) => {
    setActioningEmail(email)
    setError(null)
    setSuccessMessage(null)
    
    try {
      const { error } = await supabase
        .from("waitlist")
        .update({ status: "rejected" })
        .eq("email", email)
      
      if (error) throw error
      
      // Update local state
      setWaitlistEntries(prev => 
        prev.map(entry => 
          entry.email === email 
            ? { ...entry, status: "rejected" } 
            : entry
        )
      )
      
      setSuccessMessage(`Rejected ${email}`)
    } catch (err: any) {
      console.error("Error rejecting user:", err)
      setError(err.message || "An error occurred while rejecting the user")
    } finally {
      setActioningEmail(null)
    }
  }

  // Resend invite to a user
  const handleResendInvite = async (email: string) => {
    setActioningEmail(email)
    setError(null)
    setSuccessMessage(null)
    
    try {
      const response = await fetch("/api/admin/resend-invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      
      const result = await response.json()
      
      if (!response.ok) {
        throw new Error(result.error || "Failed to resend invite")
      }
      
      // Update local state based on the response
      if (result.data.status === "converted") {
        // User was already registered, update status to converted
        setWaitlistEntries(prev => 
          prev.map(entry => 
            entry.email === email 
              ? { ...entry, status: "converted" } 
              : entry
          )
        )
        setSuccessMessage(`${email} was already registered - status updated to converted`)
      } else {
        // Normal resend, update invited_at timestamp
        setWaitlistEntries(prev => 
          prev.map(entry => 
            entry.email === email 
              ? { ...entry, invited_at: result.data.invited_at } 
              : entry
          )
        )
        setSuccessMessage(`Successfully resent invite to ${email}`)
      }
    } catch (err: any) {
      console.error("Error resending invite:", err)
      setError(err.message || "An error occurred while resending the invite")
    } finally {
      setActioningEmail(null)
    }
  }

  // Discard an invite (reset to pending)
  const handleDiscardInvite = async (email: string) => {
    setActioningEmail(email)
    setError(null)
    setSuccessMessage(null)
    
    try {
      const response = await fetch("/api/admin/discard-invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      
      const result = await response.json()
      
      if (!response.ok) {
        throw new Error(result.error || "Failed to discard invite")
      }
      
      // Update local state
      setWaitlistEntries(prev => 
        prev.map(entry => 
          entry.email === email 
            ? { ...entry, status: "pending", invited_at: null } 
            : entry
        )
      )
      
      setSuccessMessage(`Successfully discarded invite for ${email}`)
    } catch (err: any) {
      console.error("Error discarding invite:", err)
      setError(err.message || "An error occurred while discarding the invite")
    } finally {
      setActioningEmail(null)
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return <Badge variant="secondary" className="bg-yellow-500/20 text-yellow-300">Pending</Badge>
      case "approved":
        return <Badge variant="secondary" className="bg-blue-500/20 text-blue-300">Approved</Badge>
      case "invited":
        return <Badge variant="secondary" className="bg-green-500/20 text-green-300">Invited</Badge>
      case "rejected":
        return <Badge variant="secondary" className="bg-red-500/20 text-red-300">Rejected</Badge>
      case "converted":
        return <Badge variant="secondary" className="bg-purple-500/20 text-purple-300">Registered</Badge>
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "—"
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(dateString))
  }

  if (isLoading) {
    return (
      <div className="text-center py-8">
        <RefreshCw className="h-8 w-8 animate-spin mx-auto text-blue-400 mb-2" />
        <p className="text-blue-200">Loading waitlist data...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with refresh button */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-semibold text-white">Waitlist Entries</h2>
          <p className="text-blue-200 text-sm">{waitlistEntries.length} total entries</p>
        </div>
        <Button
          onClick={loadWaitlist}
          variant="outline"
          size="sm"
          className="border-blue-500 text-blue-400 hover:bg-blue-950"
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <div className="rounded-lg border border-green-500/20 bg-green-500/10 p-4 text-green-300">
          {successMessage}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-red-300">
          {error}
        </div>
      )}

      {/* Waitlist Table */}
      <div className="rounded-lg border border-blue-900/30 bg-blue-950/10 overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-blue-900/30 hover:bg-blue-950/20">
              <TableHead className="text-blue-300 font-medium">Email</TableHead>
              <TableHead className="text-blue-300 font-medium">Status</TableHead>
              <TableHead className="text-blue-300 font-medium">Joined</TableHead>
              <TableHead className="text-blue-300 font-medium">Invited</TableHead>
              <TableHead className="text-blue-300 font-medium text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {waitlistEntries.map((entry) => (
              <TableRow key={entry.id} className="border-blue-900/30 hover:bg-blue-950/20">
                <TableCell className="font-medium text-white">{entry.email}</TableCell>
                <TableCell>{getStatusBadge(entry.status)}</TableCell>
                <TableCell className="text-blue-200">{formatDate(entry.created_at)}</TableCell>
                <TableCell className="text-blue-200">{formatDate(entry.invited_at)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    {entry.status === "pending" && (
                      <>
                        <Button
                          onClick={() => handleApprove(entry.email)}
                          disabled={actioningEmail === entry.email}
                          size="sm"
                          className="bg-green-600 hover:bg-green-700 text-white"
                        >
                          {actioningEmail === entry.email ? (
                            <RefreshCw className="h-3 w-3 animate-spin" />
                          ) : (
                            <>
                              <Check className="h-3 w-3 mr-1" />
                              Invite
                            </>
                          )}
                        </Button>
                        <Button
                          onClick={() => handleReject(entry.email)}
                          disabled={actioningEmail === entry.email}
                          size="sm"
                          variant="destructive"
                        >
                          <X className="h-3 w-3 mr-1" />
                          Reject
                        </Button>
                      </>
                    )}
                    {entry.status === "approved" && (
                      <Button
                        onClick={() => handleApprove(entry.email)}
                        disabled={actioningEmail === entry.email}
                        size="sm"
                        className="bg-blue-600 hover:bg-blue-700 text-white"
                      >
                        {actioningEmail === entry.email ? (
                          <RefreshCw className="h-3 w-3 animate-spin" />
                        ) : (
                          <>
                            <Mail className="h-3 w-3 mr-1" />
                            Send Invite
                          </>
                        )}
                      </Button>
                    )}
                    {entry.status === "invited" && (
                      <>
                        <Button
                          onClick={() => handleResendInvite(entry.email)}
                          disabled={actioningEmail === entry.email}
                          size="sm"
                          className="bg-green-600 hover:bg-green-700 text-white"
                        >
                          {actioningEmail === entry.email ? (
                            <RefreshCw className="h-3 w-3 animate-spin" />
                          ) : (
                            <>
                              <Mail className="h-3 w-3 mr-1" />
                              Resend Invite
                            </>
                          )}
                        </Button>
                        <Button
                          onClick={() => handleDiscardInvite(entry.email)}
                          disabled={actioningEmail === entry.email}
                          size="sm"
                          variant="destructive"
                        >
                          {actioningEmail === entry.email ? (
                            <RefreshCw className="h-3 w-3 animate-spin" />
                          ) : (
                            <>
                              <Trash2 className="h-3 w-3 mr-1" />
                              Discard
                            </>
                          )}
                        </Button>
                      </>
                    )}
                    {entry.status === "converted" && (
                      <span className="text-purple-300 text-sm">User registered</span>
                    )}
                    {entry.status === "rejected" && (
                      <span className="text-red-300 text-sm">Rejected</span>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {waitlistEntries.length === 0 && (
        <div className="text-center py-12">
          <Mail className="h-12 w-12 mx-auto text-blue-400 mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">No waitlist entries</h3>
          <p className="text-blue-200">Waitlist entries will appear here when users join.</p>
        </div>
      )}
    </div>
  )
} 