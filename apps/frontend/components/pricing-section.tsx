"use client"

import { Clock } from "lucide-react"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import { motion } from "framer-motion"

export function PricingSection() {
  return (
    <section id="pricing" className="relative w-full py-16 bg-black overflow-hidden">
      {/* Background elements */}
      <div className="absolute inset-0 bg-grid opacity-20"></div>
      <div className="absolute top-40 left-0 w-full h-[500px] bg-gradient-radial opacity-30"></div>

      <div className="container relative z-10 px-4 md:px-6">
        <motion.div
          className="flex flex-col items-center justify-center space-y-4 text-center"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <div className="space-y-2">
            <div className="inline-block rounded-lg bg-blue-500/10 px-3 py-1 text-sm">
              <span className="text-gradient font-semibold">Pricing</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl text-white">
              Join the <span className="text-gradient">Waitlist</span> Today
            </h2>
            <p className="max-w-[900px] text-blue-100 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
              Be among the first to experience cf
              <span className="relative inline-block">
                0
                <span className="absolute inset-0 flex items-center justify-center">
                  <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
                </span>
              </span>{" "}
              and get access to exclusive launch pricing.
            </p>
          </div>
        </motion.div>

        <motion.div
          className="mx-auto max-w-3xl mt-8 rounded-xl border border-blue-900/30 bg-blue-950/10 p-8 backdrop-blur-sm"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <div className="flex flex-col md:flex-row items-center gap-6 md:gap-10">
            <div className="flex-shrink-0 w-16 h-16 md:w-24 md:h-24 rounded-full bg-blue-500/20 flex items-center justify-center">
              <Clock className="w-8 h-8 md:w-12 md:h-12 text-blue-300" />
            </div>
            <div className="flex-1 text-center md:text-left">
              <h3 className="text-xl md:text-2xl font-bold text-white mb-2">Pricing Details Coming Soon</h3>
              <p className="text-blue-200 mb-4">
                We're currently finalizing our pricing plans. Join our waitlist to be the first to know when pricing is
                announced and to secure early access pricing.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center md:justify-start">
                <Button
                  className="bg-blue-500 hover:bg-blue-600 text-white animated-filled-button text-xs h-8 px-4"
                  asChild
                >
                  <Link href="/waitlist">Join Waitlist</Link>
                </Button>
                <Button
                  variant="outline"
                  className="border-blue-500 text-blue-400 hover:bg-blue-950 animated-button text-xs h-8 px-4"
                  asChild
                >
                  <Link href="#faq">Learn More</Link>
                </Button>
              </div>
            </div>
          </div>
          <div className="mt-8 pt-6 border-t border-blue-900/30 text-center">
            <p className="text-blue-300 text-sm">
              Early access members will receive special pricing and priority support.
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
