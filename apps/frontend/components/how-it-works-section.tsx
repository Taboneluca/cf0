"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import Image from "next/image"
import { motion, useAnimation } from "framer-motion"
import { ChevronLeft, ChevronRight } from "lucide-react"

export function HowItWorksSection() {
  const [activeStep, setActiveStep] = useState(0)
  const sectionRef = useRef<HTMLDivElement>(null)
  const touchStartX = useRef<number | null>(null)
  const [isSwiping, setIsSwiping] = useState(false)
  const [swipeDirection, setSwipeDirection] = useState<string | null>(null)
  const controls = useAnimation()
  const swipeThreshold = 50 // Minimum distance to trigger a swipe
  const swipeCooldown = useRef<boolean>(false)

  const steps = [
    {
      step: 1,
      title: "Sign Up",
      description: "Create your account in seconds and invite your team members.",
      color: "from-blue-500/20 to-blue-500/5",
      image: "/signup-preview.png",
    },
    {
      step: 2,
      title: "Create Project",
      description: "Set up your first project and customize it to fit your workflow.",
      color: "from-cyan-500/20 to-cyan-500/5",
      image: "/project-preview.png",
    },
    {
      step: 3,
      title: "Track Progress",
      description: "Monitor tasks, collaborate with your team, and celebrate milestones.",
      color: "from-blue-300/20 to-blue-300/5",
      image: "/progress-preview.png",
    },
  ]

  const handleNextStep = useCallback(() => {
    if (swipeCooldown.current) return

    setSwipeDirection("right")
    controls.start({
      x: [-20, 0],
      opacity: [0, 1],
      transition: { duration: 0.3 },
    })
    setActiveStep((prev) => (prev === steps.length - 1 ? 0 : prev + 1))

    // Set cooldown to prevent rapid swiping
    swipeCooldown.current = true
    setTimeout(() => {
      swipeCooldown.current = false
    }, 300)
  }, [steps.length, controls])

  const handlePrevStep = useCallback(() => {
    if (swipeCooldown.current) return

    setSwipeDirection("left")
    controls.start({
      x: [20, 0],
      opacity: [0, 1],
      transition: { duration: 0.3 },
    })
    setActiveStep((prev) => (prev === 0 ? steps.length - 1 : prev - 1))

    // Set cooldown to prevent rapid swiping
    swipeCooldown.current = true
    setTimeout(() => {
      swipeCooldown.current = false
    }, 300)
  }, [steps.length, controls])

  // Handle keyboard navigation
  useEffect(() => {
    if (typeof window === "undefined") return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        handleNextStep()
      } else if (e.key === "ArrowLeft") {
        handlePrevStep()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => {
      window.removeEventListener("keydown", handleKeyDown)
    }
  }, [handleNextStep, handlePrevStep])

  // Improved touchpad/swipe gestures
  useEffect(() => {
    const section = sectionRef.current
    if (!section) return

    // Improved wheel event handling for touchpads
    const handleWheel = (e: WheelEvent) => {
      // Only handle horizontal scrolling with touchpad
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY) && Math.abs(e.deltaX) > 10) {
        e.preventDefault()

        // Debounce the wheel event to prevent too many triggers
        if (swipeCooldown.current) return
        swipeCooldown.current = true

        if (e.deltaX > 0) {
          handleNextStep()
        } else {
          handlePrevStep()
        }

        setTimeout(() => {
          swipeCooldown.current = false
        }, 300)
      }
    }

    // Touch events for mobile devices
    const handleTouchStart = (e: TouchEvent) => {
      touchStartX.current = e.touches[0].clientX
      setIsSwiping(true)
    }

    const handleTouchMove = (e: TouchEvent) => {
      if (touchStartX.current === null) return

      const currentX = e.touches[0].clientX
      const diff = touchStartX.current - currentX

      // Prevent page scrolling when swiping horizontally
      if (Math.abs(diff) > 10) {
        e.preventDefault()
      }
    }

    const handleTouchEnd = (e: TouchEvent) => {
      if (touchStartX.current === null) return

      const endX = e.changedTouches[0].clientX
      const diffX = endX - touchStartX.current

      if (Math.abs(diffX) > swipeThreshold) {
        if (diffX > 0) {
          handlePrevStep()
        } else {
          handleNextStep()
        }
      }

      touchStartX.current = null
      setIsSwiping(false)
    }

    section.addEventListener("wheel", handleWheel, { passive: false })
    section.addEventListener("touchstart", handleTouchStart, { passive: true })
    section.addEventListener("touchmove", handleTouchMove, { passive: false })
    section.addEventListener("touchend", handleTouchEnd, { passive: true })

    return () => {
      section.removeEventListener("wheel", handleWheel)
      section.removeEventListener("touchstart", handleTouchStart)
      section.removeEventListener("touchmove", handleTouchMove)
      section.removeEventListener("touchend", handleTouchEnd)
    }
  }, [handleNextStep, handlePrevStep])

  return (
    <section id="how-it-works" className="relative w-full py-16 bg-black overflow-hidden" ref={sectionRef}>
      {/* Background elements */}
      <div className="absolute inset-0 bg-grid opacity-20"></div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-radial opacity-30"></div>

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
              <span className="text-gradient font-semibold">How It Works</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl text-white">
              Get Set Up in <span className="text-gradient">Minutes</span>, Start Moving Fast
            </h2>
            <p className="max-w-[900px] text-blue-100 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
              Getting started with cf
              <span className="relative inline-block">
                0
                <span className="absolute inset-0 flex items-center justify-center">
                  <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
                </span>
              </span>{" "}
              is simple and straightforward. Be up and running in no time.
            </p>
          </div>
        </motion.div>

        <div className="mx-auto max-w-5xl py-8">
          <div className="flex flex-col lg:flex-row gap-8">
            <div className="lg:w-1/3">
              {steps.map((step, index) => (
                <motion.div
                  key={step.step}
                  className={`relative flex flex-col space-y-2 rounded-lg border p-6 mb-4 cursor-pointer transition-all duration-300 ${
                    activeStep === index
                      ? "bg-gradient-to-br " + step.color + " border-blue-500/20 shadow-lg"
                      : "bg-black/50 hover:bg-black border-blue-900/30"
                  }`}
                  onClick={() => setActiveStep(index)}
                  whileHover={{ x: activeStep === index ? 0 : 5 }}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.3, delay: 0.1 * index }}
                  tabIndex={0}
                  role="button"
                  aria-pressed={activeStep === index}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      setActiveStep(index)
                      e.preventDefault()
                    }
                  }}
                >
                  <div className="flex items-center gap-4">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-full ${
                        activeStep === index ? "bg-blue-500" : "bg-blue-500/20"
                      } text-lg font-bold ${activeStep === index ? "text-white" : "text-blue-400"}`}
                    >
                      {step.step}
                    </div>
                    <h3 className="text-xl font-bold text-white">{step.title}</h3>
                  </div>
                  <p className="text-blue-200">{step.description}</p>
                </motion.div>
              ))}
            </div>

            <motion.div
              className="lg:w-2/3 relative"
              initial={{ opacity: 0, scale: 0.9 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              animate={controls}
              key={activeStep} // Force re-render on step change
            >
              <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1/2 z-10">
                <button
                  onClick={handlePrevStep}
                  className="p-2 rounded-full bg-blue-900/50 text-blue-300 hover:bg-blue-900/70 transition-colors"
                  aria-label="Previous step"
                >
                  <ChevronLeft className="h-6 w-6" />
                </button>
              </div>

              <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 z-10">
                <button
                  onClick={handleNextStep}
                  className="p-2 rounded-full bg-blue-900/50 text-blue-300 hover:bg-blue-900/70 transition-colors"
                  aria-label="Next step"
                >
                  <ChevronRight className="h-6 w-6" />
                </button>
              </div>

              <div
                className={`relative overflow-hidden rounded-xl border border-blue-900/50 glass p-2 shadow-xl h-full ${
                  isSwiping ? "cursor-grabbing" : "cursor-grab"
                }`}
              >
                <div
                  className={`absolute -top-20 -left-20 w-60 h-60 rounded-full bg-gradient-to-br ${steps[activeStep].color} blur-3xl opacity-60`}
                ></div>
                <div
                  className={`absolute -bottom-20 -right-20 w-60 h-60 rounded-full bg-gradient-to-tl ${steps[activeStep].color} blur-3xl opacity-60`}
                ></div>
                <Image
                  src={steps[activeStep].image || "/workflow-preview.png"}
                  alt={steps[activeStep].title}
                  width={800}
                  height={500}
                  className="w-full h-full object-cover rounded-lg"
                />
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="bg-black/70 px-6 py-4 rounded-lg backdrop-blur-sm">
                    <h4 className="text-xl font-bold text-white mb-2">{steps[activeStep].title}</h4>
                    <p className="text-blue-200">{steps[activeStep].description}</p>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>

        <div className="flex justify-center mt-6">
          <div className="flex gap-2">
            {steps.map((_, index) => (
              <button
                key={index}
                className={`w-3 h-3 rounded-full transition-all duration-300 ${
                  activeStep === index ? "bg-blue-500 w-6" : "bg-blue-500/30"
                }`}
                onClick={() => setActiveStep(index)}
                aria-label={`Go to step ${index + 1}`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
