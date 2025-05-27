"use client"

import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Logo } from "@/components/logo"
import { AlertCircle, Clock, Mail } from "lucide-react"

export default function LinkExpiredPage() {
  const searchParams = useSearchParams()
  const message = searchParams?.get("message") || "Your invitation link has expired."

  return (
    <div className="min-h-screen bg-black flex items-center justify-center p-4">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <Logo size="lg" clickable={false} className="justify-center mb-8" />
          <div className="bg-red-950/20 border border-red-500/30 rounded-lg p-6 mb-6">
            <AlertCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
            <h1 className="text-2xl font-bold text-white mb-2">Link Expired</h1>
            <p className="text-red-200 mb-4">{message}</p>
            <div className="flex items-center justify-center gap-2 text-red-300 text-sm">
              <Clock className="h-4 w-4" />
              <span>Invitation links expire for security reasons</span>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-blue-950/20 border border-blue-500/30 rounded-lg p-4">
            <h2 className="text-lg font-semibold text-blue-200 mb-2 flex items-center gap-2">
              <Mail className="h-5 w-5" />
              What can you do?
            </h2>
            <ul className="text-blue-200 text-sm space-y-2">
              <li>• Contact our support team for a new invitation</li>
              <li>• Check if you have a more recent invitation email</li>
              <li>• Make sure to use the invitation link within 24 hours</li>
            </ul>
          </div>

          <div className="space-y-3">
            <Button
              asChild
              className="w-full bg-blue-600 hover:bg-blue-700 text-white"
            >
              <Link href="/waitlist">
                Join Waitlist Again
              </Link>
            </Button>
            
            <Button
              asChild
              variant="outline"
              className="w-full border-blue-500 text-blue-300 hover:bg-blue-950"
            >
              <Link href="/login">
                Try to Sign In
              </Link>
            </Button>
            
            <Button
              asChild
              variant="ghost"
              className="w-full text-blue-400 hover:text-blue-300"
            >
              <Link href="/">
                Back to Home
              </Link>
            </Button>
          </div>
        </div>

        <div className="text-center">
          <p className="text-blue-300 text-sm">
            Need help?{" "}
            <Link href="mailto:support@cf0.ai" className="text-blue-400 hover:text-blue-300 underline">
              Contact Support
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
} 