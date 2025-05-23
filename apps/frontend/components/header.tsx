"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { motion } from "framer-motion"
import { Logo } from "./logo"
import { LayoutDashboard } from "lucide-react"

export function Header() {
  const [scrolled, setScrolled] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!mounted || typeof window === "undefined") return

    const handleScroll = () => {
      setScrolled(window.scrollY > 10)
    }

    window.addEventListener("scroll", handleScroll)
    return () => window.removeEventListener("scroll", handleScroll)
  }, [mounted])

  return (
    <header
      className={`sticky top-0 z-40 w-full transition-all duration-200 ${
        scrolled ? "bg-black/80 backdrop-blur-md border-b border-blue-900/20" : "bg-transparent"
      }`}
    >
      <div className="w-full flex h-16 items-center justify-between px-4 md:px-6">
        {/* Logo - Left side with proper z-index */}
        <motion.div
          className="flex-shrink-0 ml-4 relative z-50"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
        >
          <Logo clickable={true} />
        </motion.div>

        {/* Navigation - Center */}
        <nav className="hidden md:flex items-center justify-center gap-6 absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2">
          <Link href="#features" className="text-sm font-medium text-blue-100 hover:text-white transition-colors">
            Features
          </Link>
          <Link href="#how-it-works" className="text-sm font-medium text-blue-100 hover:text-white transition-colors">
            How It Works
          </Link>
          <Link href="#pricing" className="text-sm font-medium text-blue-100 hover:text-white transition-colors">
            Pricing
          </Link>
          <Link href="#faq" className="text-sm font-medium text-blue-100 hover:text-white transition-colors">
            FAQ
          </Link>
        </nav>

        {/* Buttons - Right side */}
        <motion.div
          className="flex items-center gap-2 mr-4 relative z-50"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
        >
          <Button
            variant="outline"
            size="sm"
            className="border-blue-500 text-blue-400 hover:bg-blue-950 animated-button text-xs h-8 px-2"
            asChild
          >
            <Link href="/dashboard">
              <LayoutDashboard className="mr-1 h-3 w-3" />
              <span className="text-xs">Dashboard</span>
            </Link>
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="border-blue-500 text-blue-400 hover:bg-blue-950 animated-button text-xs h-8 px-2"
            asChild
          >
            <Link href="/waitlist">
              <span className="text-xs">Join Waitlist</span>
            </Link>
          </Button>
        </motion.div>
      </div>
    </header>
  )
}
