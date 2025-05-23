"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { motion } from "framer-motion"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { Envelope } from "@/components/envelope"

export default function WaitlistConfirmation() {
  const [email, setEmail] = useState("")

  useEffect(() => {
    // Get email from localStorage
    const storedEmail = localStorage.getItem("waitlistEmail") || ""
    setEmail(storedEmail)
  }, [])

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
            <div className="flex flex-col items-center justify-center text-center max-w-3xl mx-auto">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="mb-8"
              >
                <h1 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl text-white mb-4">
                  You're on the <span className="text-gradient">Waitlist</span>!
                </h1>
                <p className="text-xl text-blue-100">
                  Thank you for joining the cf
                  <span className="relative inline-block">
                    0
                    <span className="absolute inset-0 flex items-center justify-center">
                      <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
                    </span>
                  </span>{" "}
                  waitlist. We'll notify you when we're ready to launch.
                </p>
                {email && (
                  <p className="text-blue-300 mt-2">
                    Confirmation sent to: <span className="font-semibold">{email}</span>
                  </p>
                )}
              </motion.div>

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5, delay: 0.3 }}
                className="my-12"
              >
                <Envelope />
              </motion.div>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.6 }}
                className="mt-8"
              >
                <p className="text-blue-100 mb-6">
                  Check your inbox for a confirmation email. Be sure to check your spam folder if you don't see it.
                </p>
                <Button
                  asChild
                  className="bg-blue-500 hover:bg-blue-600 text-white text-xs h-8 px-4 animated-filled-button"
                >
                  <Link href="/">Return to Home</Link>
                </Button>
              </motion.div>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  )
}
