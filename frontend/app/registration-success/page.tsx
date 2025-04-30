import type { Metadata } from "next"
import Link from "next/link"

export const metadata: Metadata = {
  title: "Registration Success - CF0",
  description: "Your account has been created successfully",
}

export default function RegistrationSuccessPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
        <div className="mx-auto w-full max-w-md space-y-6">
          <div className="space-y-2 text-center">
            <h1 className="text-3xl font-bold">Registration Successful!</h1>
            <p className="text-gray-500">Your account has been created successfully.</p>
          </div>
          <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-600">
            <p>We've sent a confirmation email to your address. Please verify your email to access your account.</p>
          </div>
          <div className="text-center">
            <Link
              href="/login"
              className="inline-flex h-10 items-center justify-center rounded-md bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600 focus-visible:outline-none focus-visible:ring-2"
            >
              Go to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
