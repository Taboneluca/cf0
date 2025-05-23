import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"
import { LoginForm } from "@/components/auth/login-form"

export const metadata: Metadata = {
  title: "Login - CF0",
  description: "Login to your CF0 account",
}

// Loading fallback for Suspense
function LoginFormSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-10 bg-gray-200 rounded-md w-full"></div>
      <div className="h-10 bg-gray-200 rounded-md w-full"></div>
      <div className="h-10 bg-blue-200 rounded-md w-full"></div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
        <div className="mx-auto w-full max-w-md space-y-6">
          <div className="space-y-2 text-center">
            <h1 className="text-3xl font-bold">Welcome back</h1>
            <p className="text-gray-500">Enter your email to sign in to your account</p>
          </div>
          <Suspense fallback={<LoginFormSkeleton />}>
            <LoginForm />
          </Suspense>
          <div className="text-center text-sm">
            Don&apos;t have an account?{" "}
            <Link href="/waitlist-status" className="underline">
              Check waitlist status
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
