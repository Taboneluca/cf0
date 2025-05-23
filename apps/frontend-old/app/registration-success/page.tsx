import type { Metadata } from "next"
import Link from "next/link"
import CF0Logo from "@/components/CF0Logo"

export const metadata: Metadata = {
  title: "Registration Success - CF0",
  description: "Your account has been created successfully",
}

export default function RegistrationSuccessPage() {
  return (
    <div className="flex min-h-screen flex-col bg-black text-white">
      <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
        <div className="mx-auto w-full max-w-md space-y-6">
          <div className="flex flex-col items-center space-y-6">
            <CF0Logo size={64} className="text-cf0-500" />
            <div className="space-y-2 text-center">
              <h1 className="text-3xl font-bold font-mono">Registration Successful!</h1>
              <p className="text-gray-300 font-mono">Your account has been created successfully.</p>
            </div>
          </div>
          <div className="rounded-lg border border-green-700 bg-green-900 bg-opacity-30 p-4 text-sm text-green-400 font-mono">
            <p>We've sent a confirmation email to your address. Please verify your email to access your account.</p>
          </div>
          <div className="text-center">
            <Link
              href="/login"
              className="inline-flex h-10 items-center justify-center rounded-md bg-cf0-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-cf0-900 focus-visible:outline-none focus-visible:ring-2 font-mono"
            >
              Go to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
