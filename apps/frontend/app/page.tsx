"use client"

import { useEffect, useState } from "react"
import { HeroSection } from "@/components/hero-section"
import { FeaturesSection } from "@/components/features-section"
import { FinancialModelSection } from "@/components/financial-model-section"
import { HowItWorksSection } from "@/components/how-it-works-section"
import { PricingSection } from "@/components/pricing-section"
import { FaqSection } from "@/components/faq-section"
import { Footer } from "@/components/footer"
import { Header } from "@/components/header"
import { motion, useScroll, useSpring } from "framer-motion"

export default function Home() {
  const [mounted, setMounted] = useState(false)
  
  // Only initialize framer-motion hooks on the client
  const { scrollYProgress } = typeof window !== "undefined" ? useScroll() : { scrollYProgress: { get: () => 0 } as any }
  const scaleX = typeof window !== "undefined" ? useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001,
  }) : { get: () => 0 } as any

  // Ensure component only hydrates on client
  useEffect(() => {
    setMounted(true)
  }, [])

  // Add smooth scrolling for anchor links - only on client
  useEffect(() => {
    if (!mounted || typeof window === "undefined") return

    const handleAnchorClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      const anchor = target.closest('a[href^="#"]')

      if (anchor) {
        e.preventDefault()
        const targetId = anchor.getAttribute("href")
        if (targetId && targetId !== "#") {
          const targetElement = document.querySelector(targetId)
          if (targetElement) {
            targetElement.scrollIntoView({
              behavior: "smooth",
            })
          }
        }
      }
    }

    document.addEventListener("click", handleAnchorClick)
    return () => document.removeEventListener("click", handleAnchorClick)
  }, [mounted])

  // Prevent hydration mismatch
  if (!mounted) {
    return (
      <div className="flex min-h-screen flex-col bg-black">
        <Header />
        <main className="flex-1">
          <HeroSection />
          <FeaturesSection />
          <FinancialModelSection />
          <HowItWorksSection />
          <PricingSection />
          <FaqSection />
        </main>
        <Footer />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col bg-black">
      <motion.div className="fixed top-0 left-0 right-0 h-1 bg-blue-500 z-50 origin-left" style={{ scaleX }} />
      <Header />
      <main className="flex-1">
        <HeroSection />
        {/* Consistent spacing between all sections */}
        <FeaturesSection />
        <FinancialModelSection />
        <HowItWorksSection />
        <PricingSection />
        <FaqSection />
      </main>
      <Footer />
    </div>
  )
}
