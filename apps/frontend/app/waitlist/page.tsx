"use client"

import type React from "react"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { motion } from "framer-motion"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"

export default function Waitlist() {
  const [email, setEmail] = useState("")
  const [name, setName] = useState("")
  const [company, setCompany] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email) return
    
    setIsSubmitting(true)
    setError(null)

    try {
      const response = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, name, company }),
      })
      
      const result = await response.json()
      
      if (!response.ok) {
        throw new Error(result.error || "Failed to join waitlist")
      }

      // Store email for confirmation page
      localStorage.setItem("waitlistEmail", email)
      router.push("/waitlist-confirmation")
    } catch (err: any) {
      console.error("Error submitting to waitlist:", err)
      setError(err.message || "An error occurred. Please try again.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-black">
      <Header />
      <main className="flex-1">
        <section className="relative w-full py-16 md:py-24 lg:py-32 overflow-hidden bg-black">
          {/* Background elements */}
          <div className="absolute inset-0 bg-grid opacity-20"></div>
          <div className="absolute top-20 left-10 w-72 h-72 bg-blue-500/20 rounded-full blur-3xl"></div>
          <div className="absolute bottom-20 right-10 w-96 h-96 bg-cyan-400/20 rounded-full blur-3xl"></div>

          <div className="container relative z-10 px-4 md:px-6">
            <div className="flex flex-col lg:flex-row gap-12 items-center">
              <motion.div
                className="flex-1"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.5 }}
              >
                <h1 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl text-white mb-4">
                  Join the{" "}
                  <span className="text-gradient">
                    cf
                    <span className="relative inline-block">
                      0
                      <span className="absolute inset-0 flex items-center justify-center">
                        <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
                      </span>
                    </span>
                  </span>{" "}
                  Waitlist
                </h1>
                <p className="text-xl text-blue-100 mb-6">
                  Be among the first to experience the power of AI-enhanced spreadsheets. Sign up now to secure your
                  spot.
                </p>
                <ul className="space-y-3 mb-8">
                  {[
                    "Early access to all features",
                    "Priority onboarding and support",
                    "Influence product development",
                    "Special launch pricing",
                  ].map((item, index) => (
                    <motion.li
                      key={index}
                      className="flex items-center gap-2 text-blue-200"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, delay: 0.3 + index * 0.1 }}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="h-5 w-5 text-blue-400"
                      >
                        <polyline points="20 6 9 17 4 12"></polyline>
                      </svg>
                      <span>{item}</span>
                    </motion.li>
                  ))}
                </ul>
              </motion.div>

              <motion.div
                className="w-full max-w-md"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
              >
                <div className="rounded-xl border border-blue-900/30 bg-blue-950/20 p-6 backdrop-blur-sm">
                  <h2 className="text-2xl font-bold text-white mb-6">Reserve Your Spot</h2>
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                      <label htmlFor="name" className="text-sm font-medium text-blue-100">
                        Name
                      </label>
                      <Input
                        id="name"
                        type="text"
                        placeholder="Your name"
                        className="bg-blue-950/30 border-blue-900/50 text-white"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="email" className="text-sm font-medium text-blue-100">
                        Email <span className="text-blue-400">*</span>
                      </label>
                      <Input
                        id="email"
                        type="email"
                        placeholder="you@example.com"
                        className="bg-blue-950/30 border-blue-900/50 text-white"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="company" className="text-sm font-medium text-blue-100">
                        Company
                      </label>
                      <Input
                        id="company"
                        type="text"
                        placeholder="Your company (optional)"
                        className="bg-blue-950/30 border-blue-900/50 text-white"
                        value={company}
                        onChange={(e) => setCompany(e.target.value)}
                      />
                    </div>
                    <Button
                      type="submit"
                      disabled={isSubmitting}
                      className="w-full bg-blue-500 hover:bg-blue-600 text-white font-medium text-xs h-8 animated-filled-button"
                    >
                      {isSubmitting ? "Joining..." : "Join Waitlist"}
                    </Button>
                    {error && (
                      <p className="text-sm text-red-400 text-center mt-2">{error}</p>
                    )}
                    <p className="text-xs text-blue-300 text-center mt-4">
                      By joining, you agree to our Terms of Service and Privacy Policy.
                    </p>
                  </form>
                </div>
              </motion.div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}
