"use client"

import { Button } from "@/components/ui/button"
import { motion } from "framer-motion"
import Link from "next/link"

export function CtaSection() {
  return (
    <section className="relative w-full py-16 md:py-24 lg:py-32 overflow-hidden">
      {/* Background elements */}
      <div className="absolute inset-0 bg-gradient-to-r from-blue-900/90 to-blue-600/90"></div>
      <div className="absolute top-0 right-0 w-1/3 h-full bg-gradient-to-l from-blue-500/10 to-transparent"></div>
      <div className="absolute bottom-0 left-0 w-1/3 h-1/2 bg-gradient-to-t from-blue-500/10 to-transparent"></div>

      {/* Floating elements */}
      <div className="absolute top-20 left-[10%] w-20 h-20 rounded-full bg-white/10 animate-float"></div>
      <div className="absolute top-40 right-[15%] w-16 h-16 rounded-full bg-white/10 animate-float-slow"></div>
      <div className="absolute bottom-20 left-[20%] w-24 h-24 rounded-full bg-white/10 animate-float-fast"></div>
      <div className="absolute bottom-40 right-[25%] w-12 h-12 rounded-full bg-white/10 animate-float"></div>

      <div className="container relative z-10 px-4 md:px-6">
        <motion.div
          className="flex flex-col items-center justify-center space-y-8 text-center"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <motion.div
            className="space-y-4"
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <h2 className="text-4xl font-bold tracking-tighter sm:text-5xl md:text-6xl text-white">
              Be Among the <span className="underline decoration-white/50 decoration-4 underline-offset-4">First</span>{" "}
              to Experience cf
              <span className="relative inline-block">
                0
                <span className="absolute inset-0 flex items-center justify-center">
                  <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
                </span>
              </span>
            </h2>
            <p className="mx-auto max-w-[700px] text-xl text-blue-100">
              Join our waitlist today and get early access when we launch.
            </p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <Button
              asChild
              className="bg-white text-blue-700 hover:bg-white/90 font-semibold px-4 py-2 h-8 text-xs rounded-md shadow-lg hover:shadow-xl transition-all duration-300 animated-button"
            >
              <Link href="/waitlist">Join Waitlist</Link>
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </section>
  )
}
