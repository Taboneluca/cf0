import type { Metadata } from "next"
import Link from "next/link"
import { LoginForm } from "@/components/auth/login-form"

export const metadata: Metadata = {
  title: "Login - CF0",
  description: "Login to your CF0 account",
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
          <LoginForm />
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
