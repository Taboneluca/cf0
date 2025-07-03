"use client"

import { useState } from "react"
import {
  CheckCircle,
  BarChart4,
  TableProperties,
  Calculator,
  TrendingUp,
  FileSpreadsheet,
  PieChart,
  ArrowUpDown,
  Briefcase,
} from "lucide-react"
import { motion } from "framer-motion"

export function FeaturesSection() {
  const [hoveredFeature, setHoveredFeature] = useState<number | null>(null)

  const features = [
    {
      title: "Financial Modeling",
      description:
        "Build sophisticated financial models with advanced formulas and functions for valuation, LBO, M&A, and DCF analysis.",
      icon: <Calculator className="h-8 w-8 text-blue-400" />,
      color: "bg-blue-500/10 border-blue-500/20",
      hoverColor: "bg-blue-500/20 border-blue-500/30",
    },
    {
      title: "Data Visualization",
      description:
        "Transform complex financial data into compelling charts and graphs that tell the story behind the numbers.",
      icon: <BarChart4 className="h-8 w-8 text-cyan-400" />,
      color: "bg-cyan-500/10 border-cyan-500/20",
      hoverColor: "bg-cyan-500/20 border-cyan-500/30",
    },
    {
      title: "Data Cleaning & Preparation",
      description: "Efficiently clean, transform, and prepare large datasets for analysis with AI-powered tools.",
      icon: <TableProperties className="h-8 w-8 text-blue-300" />,
      color: "bg-blue-300/10 border-blue-300/20",
      hoverColor: "bg-blue-300/20 border-blue-300/30",
    },
    {
      title: "Professional Formatting",
      description:
        "Create presentation-ready outputs with consistent, professional formatting that meets investment banking standards.",
      icon: <FileSpreadsheet className="h-8 w-8 text-sky-400" />,
      color: "bg-sky-500/10 border-sky-500/20",
      hoverColor: "bg-sky-500/20 border-sky-500/30",
    },
  ]

  const advancedFeatures = [
    {
      title: "Scenario Analysis",
      description: "Run multiple scenarios simultaneously to stress-test your models and identify key sensitivities.",
      icon: <ArrowUpDown className="h-8 w-8 text-blue-400" />,
      color: "bg-blue-500/10 border-blue-500/20",
      hoverColor: "bg-blue-500/20 border-blue-500/30",
      comingSoon: false,
    },
    {
      title: "Valuation Tools",
      description: "Access industry-specific valuation multiples and benchmarks to support your analysis.",
      icon: <TrendingUp className="h-8 w-8 text-green-400" />,
      color: "bg-green-500/10 border-green-500/20",
      hoverColor: "bg-green-500/20 border-green-500/30",
      comingSoon: false,
    },
    {
      title: "Pitch Book Generation",
      description: "Automatically generate professional pitch books and presentations from your financial models.",
      icon: <Briefcase className="h-8 w-8 text-amber-400" />,
      color: "bg-amber-500/10 border-amber-500/20",
      hoverColor: "bg-amber-500/20 border-amber-500/30",
      comingSoon: true,
    },
    {
      title: "Market Data Integration",
      description: "Connect to real-time market data and financial information to keep your models current.",
      icon: <PieChart className="h-8 w-8 text-purple-400" />,
      color: "bg-purple-500/10 border-purple-500/20",
      hoverColor: "bg-purple-500/20 border-purple-500/30",
      comingSoon: true,
    },
  ]

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  }

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
  }

  return (
    <section id="features" className="relative w-full py-16 bg-black overflow-hidden">
      {/* Background elements */}
      <div className="absolute inset-0 bg-grid opacity-20"></div>
      <div className="absolute top-0 left-0 w-full h-full bg-gradient-radial opacity-50"></div>

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
              <span className="text-gradient font-semibold">Features</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl text-white">
              Investment Banking <span className="text-gradient">Capabilities</span>
            </h2>
            <p className="max-w-[900px] text-blue-100 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
              Everything an experienced investment banker needs, powered by AI to enhance productivity and precision.
            </p>
          </div>
        </motion.div>

        <motion.div
          className="mx-auto grid max-w-5xl items-center gap-6 py-8 lg:grid-cols-2 lg:gap-12"
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
        >
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              className={`group relative overflow-hidden rounded-lg border ${
                hoveredFeature === index ? feature.hoverColor : feature.color
              } p-6 shadow-sm transition-all duration-300 card-hover`}
              variants={item}
              onMouseEnter={() => setHoveredFeature(index)}
              onMouseLeave={() => setHoveredFeature(null)}
            >
              <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-gradient-to-br from-blue-500/20 to-transparent blur-2xl transition-all duration-500 group-hover:scale-150"></div>
              <div className="relative flex flex-col space-y-4">
                <div className="flex items-center gap-3">
                  {feature.icon}
                  <h3 className="text-xl font-bold text-white">{feature.title}</h3>
                </div>
                <p className="text-blue-200">{feature.description}</p>
              </div>
            </motion.div>
          ))}
        </motion.div>

        {/* Reduced spacing between Features and Advanced Financial Tools */}
        <div className="py-6"></div>

        <motion.div
          className="mx-auto max-w-5xl items-center gap-6 lg:gap-12"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <h3 className="text-2xl font-bold tracking-tighter text-center text-white mb-8">
            Advanced <span className="text-gradient">Financial Tools</span>
          </h3>

          <div className="grid gap-6 lg:grid-cols-2 lg:gap-12">
            {advancedFeatures.map((feature, index) => (
              <motion.div
                key={feature.title}
                className={`group relative overflow-hidden rounded-lg border ${
                  feature.color
                } p-6 shadow-sm transition-all duration-300 card-hover`}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: 0.1 * index }}
                onMouseEnter={() => setHoveredFeature(index + features.length)}
                onMouseLeave={() => setHoveredFeature(null)}
              >
                <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-gradient-to-br from-blue-500/20 to-transparent blur-2xl transition-all duration-500 group-hover:scale-150"></div>
                <div className="relative flex flex-col space-y-4">
                  <div className="flex items-center gap-3">
                    {feature.icon}
                    <div>
                      <h3 className="text-xl font-bold text-white">{feature.title}</h3>
                      {feature.comingSoon && (
                        <span className="text-xs font-medium bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full">
                          Coming Soon
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-blue-200">{feature.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        <motion.div
          className="mx-auto max-w-3xl mt-8 p-6 rounded-lg border border-blue-900/30 bg-blue-950/20 backdrop-blur-sm"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <h4 className="text-xl font-bold text-white mb-4 text-center">Investment Banking Workflow Capabilities</h4>
          <div className="grid gap-3 md:grid-cols-2">
            {[
              "DCF & Valuation Models",
              "LBO & M&A Analysis",
              "Comparable Company Analysis",
              "Precedent Transaction Analysis",
              "Financial Statement Modeling",
              "Sensitivity & Scenario Analysis",
              "Capital Structure Optimization",
              "Pitch Book Automation",
              "Data Room Management",
              "Due Diligence Support",
              "Market Research Integration",
              "Regulatory Compliance Checks",
            ].map((feature, index) => (
              <motion.div
                key={feature}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: 0.05 * index }}
              >
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-blue-400 flex-shrink-0" />
                  <span className="text-blue-100">{feature}</span>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}
