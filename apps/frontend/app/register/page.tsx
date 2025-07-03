import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"
import { RegisterForm } from "@/components/auth/register-form"

export const metadata: Metadata = {
  title: "Register - CF0",
  description: "Create your CF0 account",
}

export default function RegisterPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
        <div className="mx-auto w-full max-w-md space-y-6">
          <div className="space-y-2 text-center">
            <h1 className="text-3xl font-bold">Create an account</h1>
            <p className="text-gray-500">Enter your details to create your account</p>
          </div>
          <Suspense fallback={<div className="text-center">Loading...</div>}>
            <RegisterForm />
          </Suspense>
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