import type { Metadata } from "next"
import Link from "next/link"
import { WaitlistStatusForm } from "@/components/waitlist-status-form"

export const metadata: Metadata = {
  title: "Waitlist Status - CF0",
  description: "Check your waitlist status for CF0",
}

export default function WaitlistStatusPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
        <div className="mx-auto w-full max-w-md space-y-6">
          <div className="space-y-2 text-center">
            <h1 className="text-3xl font-bold">Check Waitlist Status</h1>
            <p className="text-gray-500">Enter your email to check your waitlist status</p>
          </div>
          <WaitlistStatusForm />
          <div className="text-center text-sm">
            Already have an account?{" "}
            <Link href="/login" className="underline">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
