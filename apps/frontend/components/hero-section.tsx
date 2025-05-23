"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { motion, useScroll, useTransform } from "framer-motion"
import Link from "next/link"
import { GraduationCap } from "lucide-react"

export function HeroSection() {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 })
  const { scrollY } = useScroll()

  // Parallax effect values
  const y1 = useTransform(scrollY, [0, 500], [0, 100])
  const y2 = useTransform(scrollY, [0, 500], [0, -100])
  const opacity = useTransform(scrollY, [0, 300], [1, 0])

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY })
    }

    window.addEventListener("mousemove", handleMouseMove)
    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
    }
  }, [])

  const calculateTransform = (depth = 1) => {
    const x = ((window.innerWidth / 2 - mousePosition.x) / 50) * depth
    const y = ((window.innerHeight / 2 - mousePosition.y) / 50) * depth
    return `translate(${x}px, ${y}px)`
  }

  return (
    <section className="relative w-full py-16 md:py-20 lg:py-24 overflow-hidden bg-black">
      {/* Background elements with parallax effect */}
      <motion.div className="absolute inset-0 bg-grid opacity-30" style={{ y: y1 }}></motion.div>
      <motion.div
        className="absolute top-20 left-10 w-72 h-72 bg-blue-500/20 rounded-full blur-3xl"
        style={{
          transform: calculateTransform(0.5),
          y: y2,
          opacity,
        }}
      ></motion.div>
      <motion.div
        className="absolute bottom-20 right-10 w-96 h-96 bg-cyan-400/20 rounded-full blur-3xl"
        style={{
          transform: calculateTransform(0.3),
          y: y1,
          opacity,
        }}
      ></motion.div>

      <div className="container relative z-10 px-4 md:px-6">
        <div className="grid gap-6 lg:grid-cols-[1fr_400px] lg:gap-12 xl:grid-cols-[1fr_600px]">
          <motion.div
            className="flex flex-col justify-center space-y-4"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <motion.div
              className="inline-flex items-center gap-2 rounded-full bg-blue-500/20 px-4 py-2 text-sm"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <GraduationCap className="h-4 w-4 text-blue-300" />
              <span className="text-blue-300 font-medium">Available to all London University Students for free</span>
            </motion.div>
            <motion.h1
              className="text-3xl font-bold tracking-tighter sm:text-5xl xl:text-6xl/none glow-text text-white"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.7, delay: 0.3 }}
            >
              Spreadsheets <span className="text-gradient">Powered</span> by AI
            </motion.h1>
            <motion.p
              className="max-w-[600px] text-blue-100 md:text-xl"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.7, delay: 0.4 }}
            >
              cf0 combines the power of spreadsheets with AI to help you analyze and manipulate your data more
              efficiently.
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.5 }}
            >
              <Button
                className="bg-blue-500 hover:bg-blue-600 text-white animated-filled-button text-xs h-8 px-4"
                asChild
              >
                <Link href="/waitlist">Join Waitlist</Link>
              </Button>
            </motion.div>
          </motion.div>
          <motion.div
            className="flex items-center justify-center"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.6 }}
            style={{ transform: calculateTransform(0.1) }}
          >
            <div className="relative w-full max-w-[500px] aspect-video overflow-hidden rounded-xl border border-blue-900/50 glass p-2 shadow-xl">
              <div className="absolute -top-16 -left-16 w-32 h-32 bg-blue-500/30 rounded-full blur-2xl"></div>
              <div className="absolute -bottom-16 -right-16 w-32 h-32 bg-cyan-500/30 rounded-full blur-2xl"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="grid grid-cols-4 grid-rows-4 gap-4 w-full h-full p-6">
                  {Array.from({ length: 16 }).map((_, i) => (
                    <motion.div
                      key={i}
                      className="flex items-center justify-center bg-blue-900/30 rounded-md backdrop-blur-sm border border-blue-500/20"
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{
                        opacity: 1,
                        scale: 1,
                        transition: {
                          delay: 0.8 + i * 0.05,
                          duration: 0.5,
                        },
                      }}
                    >
                      <span className="text-blue-200 font-mono text-lg">{Math.floor(Math.random() * 100)}</span>
                    </motion.div>
                  ))}
                </div>
              </div>
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 to-black/0 pointer-events-none"></div>
            </div>
          </motion.div>
        </div>
        <motion.div
          className="mt-8 flex flex-col items-center space-y-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.8 }}
        >
          <p className="text-center text-sm text-blue-200">Trusted by data professionals worldwide</p>
          <div className="flex flex-wrap justify-center gap-8">
            {["Finance", "Analytics", "Research", "Enterprise", "Startups"].map((industry, index) => (
              <motion.div
                key={industry}
                className="flex items-center justify-center"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.8 + index * 0.1 }}
              >
                <span className="text-lg font-semibold text-blue-300">{industry}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}
