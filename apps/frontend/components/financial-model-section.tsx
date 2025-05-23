"use client"

import { motion } from "framer-motion"
import { Code, Sparkles, Zap, Clock } from "lucide-react"

export function FinancialModelSection() {
  return (
    <section className="relative w-full py-16 bg-black overflow-hidden">
      {/* Background elements */}
      <div className="absolute inset-0 bg-grid opacity-20"></div>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-radial opacity-30"></div>

      <div className="container relative z-10 px-4 md:px-6">
        <motion.div
          className="flex flex-col items-center justify-center space-y-4 text-center mb-12"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <div className="space-y-2">
            <div className="inline-block rounded-lg bg-blue-500/10 px-3 py-1 text-sm">
              <span className="text-gradient font-semibold">AI-Powered</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl text-white">
              Work Like a <span className="text-gradient">Data Expert</span>
            </h2>
            <p className="max-w-[900px] text-blue-100 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
              Let AI handle the tedious tasks while you focus on high-value analysis and strategic insights across any
              industry.
            </p>
          </div>
        </motion.div>

        <div className="grid gap-8 lg:grid-cols-2 items-center">
          <motion.div
            className="order-2 lg:order-1"
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <div className="space-y-6">
              <motion.div
                className="flex gap-4 items-start"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: 0.1 }}
              >
                <div className="bg-blue-500/20 p-3 rounded-lg">
                  <Sparkles className="h-6 w-6 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-2">Natural Language Commands</h3>
                  <p className="text-blue-200">
                    Simply type "Create a sales forecast model" or "Analyze customer churn patterns" and watch cf
                    <span className="relative inline-block">
                      0
                      <span className="absolute inset-0 flex items-center justify-center">
                        <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
                      </span>
                    </span>{" "}
                    build it instantly.
                  </p>
                </div>
              </motion.div>

              <motion.div
                className="flex gap-4 items-start"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: 0.2 }}
              >
                <div className="bg-cyan-500/20 p-3 rounded-lg">
                  <Code className="h-6 w-6 text-cyan-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-2">Smart Formula Generation</h3>
                  <p className="text-blue-200">
                    Complex formulas are generated automatically with proper cell references, reducing errors and saving
                    hours of manual work across any data analysis task.
                  </p>
                </div>
              </motion.div>

              <motion.div
                className="flex gap-4 items-start"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: 0.3 }}
              >
                <div className="bg-purple-500/20 p-3 rounded-lg">
                  <Zap className="h-6 w-6 text-purple-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-2">Instant Data Import</h3>
                  <p className="text-blue-200">
                    Pull data from various sources including databases, APIs, and files directly into your models with a
                    single command.
                  </p>
                </div>
              </motion.div>

              <motion.div
                className="flex gap-4 items-start"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: 0.4 }}
              >
                <div className="bg-green-500/20 p-3 rounded-lg">
                  <Clock className="h-6 w-6 text-green-400" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white mb-2">80% Time Savings</h3>
                  <p className="text-blue-200">
                    Tasks that typically take hours can be completed in minutes, allowing you to focus on insights and
                    strategic decision-making.
                  </p>
                </div>
              </motion.div>
            </div>
          </motion.div>

          <motion.div
            className="order-1 lg:order-2"
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <div className="relative overflow-hidden rounded-xl border border-blue-900/50 glass p-2 shadow-xl">
              <div className="absolute -top-20 -left-20 w-60 h-60 rounded-full bg-gradient-to-br from-blue-500/20 to-blue-500/5 blur-3xl opacity-60"></div>
              <div className="absolute -bottom-20 -right-20 w-60 h-60 rounded-full bg-gradient-to-tl from-cyan-500/20 to-cyan-500/5 blur-3xl opacity-60"></div>

              <div className="bg-black/80 rounded-lg p-4 overflow-hidden">
                <div className="flex items-center gap-2 mb-3 border-b border-blue-900/30 pb-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <span className="text-blue-300 text-xs ml-2">Sales Analysis - Q4_2024.xlsx</span>
                </div>

                <div className="font-mono text-xs text-blue-200 space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-blue-400">
                      cf
                      <span className="relative inline-block">
                        0
                        <span className="absolute inset-0 flex items-center justify-center">
                          <span className="h-[1px] w-[140%] bg-blue-400 -rotate-15 transform-gpu"></span>
                        </span>
                      </span>
                      &gt;
                    </span>
                    <span className="text-white">Create a sales forecast model with seasonal trends</span>
                  </div>
                  <div className="text-blue-300">Analyzing historical sales data...</div>
                  <div className="text-blue-300">Identifying seasonal patterns...</div>
                  <div className="text-blue-300">Building predictive model...</div>
                  <div className="text-blue-300">Generating forecast formulas...</div>
                  <div className="text-green-400">✓ Sales forecast model created successfully!</div>
                  <div className="mt-4 flex items-center gap-2">
                    <span className="text-blue-400">
                      cf
                      <span className="relative inline-block">
                        0
                        <span className="absolute inset-0 flex items-center justify-center">
                          <span className="h-[1px] w-[140%] bg-blue-400 -rotate-15 transform-gpu"></span>
                        </span>
                      </span>
                      &gt;
                    </span>
                    <span className="text-white">Add scenario analysis for best/worst case</span>
                  </div>
                  <div className="text-blue-300">Creating scenario models...</div>
                  <div className="text-green-400">✓ Scenario analysis complete!</div>
                  <div className="mt-4 flex items-center gap-2">
                    <span className="text-blue-400">
                      cf
                      <span className="relative inline-block">
                        0
                        <span className="absolute inset-0 flex items-center justify-center">
                          <span className="h-[1px] w-[140%] bg-blue-400 -rotate-15 transform-gpu"></span>
                        </span>
                      </span>
                      &gt;
                    </span>
                    <span className="text-white">Format for executive presentation</span>
                  </div>
                  <div className="text-blue-300">Applying professional formatting...</div>
                  <div className="text-blue-300">Creating summary dashboard...</div>
                  <div className="text-green-400">✓ Presentation-ready format applied!</div>
                  <div className="text-blue-300">Projected Q1 revenue: $2.4M - $3.1M</div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}
