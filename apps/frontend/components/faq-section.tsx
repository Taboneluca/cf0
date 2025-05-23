"use client"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"

export function FaqSection() {
  const faqs = [
    {
      question: "How does cf0 help with financial modeling?",
      answer: (
        <>
          cf
          <span className="relative inline-block">
            0
            <span className="absolute inset-0 flex items-center justify-center">
              <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
            </span>
          </span>{" "}
          combines AI with spreadsheet functionality to automate complex financial modeling tasks. You can create DCF
          models, LBO analyses, and M&A models using natural language commands. The AI understands financial concepts
          and generates accurate formulas, saving hours of manual work.
        </>
      ),
    },
    {
      question: "Can cf0 connect to financial data sources?",
      answer: (
        <>
          Yes, cf
          <span className="relative inline-block">
            0
            <span className="absolute inset-0 flex items-center justify-center">
              <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
            </span>
          </span>{" "}
          integrates with major financial data providers to pull real-time market data, company financials, and industry
          benchmarks directly into your models. This ensures your analyses are always based on the most current
          information available.
        </>
      ),
    },
    {
      question: "How accurate are the financial models created by cf0?",
      answer: (
        <>
          cf
          <span className="relative inline-block">
            0
            <span className="absolute inset-0 flex items-center justify-center">
              <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
            </span>
          </span>
          's models follow industry best practices and are built with the same rigor as those created by top investment
          banks. The AI has been trained on thousands of professional financial models to ensure accuracy and
          reliability. You always maintain full control to review and adjust any assumptions or calculations.
        </>
      ),
    },
    {
      question: "Can I import my existing Excel models into cf0?",
      answer: (
        <>
          Absolutely. cf
          <span className="relative inline-block">
            0
            <span className="absolute inset-0 flex items-center justify-center">
              <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
            </span>
          </span>{" "}
          is designed to work with your existing workflows. You can import Excel files, and cf
          <span className="relative inline-block">
            0
            <span className="absolute inset-0 flex items-center justify-center">
              <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
            </span>
          </span>{" "}
          will analyze and enhance them with AI capabilities while preserving your original structure and formulas.
        </>
      ),
    },
    {
      question: "Is my financial data secure with cf0?",
      answer: (
        <>
          Security is our top priority. cf
          <span className="relative inline-block">
            0
            <span className="absolute inset-0 flex items-center justify-center">
              <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
            </span>
          </span>{" "}
          employs bank-grade encryption and security protocols to protect your sensitive financial data. We never share
          your information with third parties, and you maintain complete ownership of all your models and data.
        </>
      ),
    },
  ]

  return (
    <section id="faq" className="relative w-full py-16 bg-black overflow-hidden">
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
              <span className="text-gradient font-semibold">FAQ</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tighter sm:text-5xl text-white">
              Everything You Need to <span className="text-gradient">Know</span>
            </h2>
            <p className="max-w-[900px] text-blue-100 md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed">
              Answers to common questions about using cf
              <span className="relative inline-block">
                0
                <span className="absolute inset-0 flex items-center justify-center">
                  <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
                </span>
              </span>{" "}
              for investment banking and financial analysis.
            </p>
          </div>
        </motion.div>

        <div className="mx-auto max-w-3xl space-y-4 py-8">
          <Accordion type="single" collapsible className="w-full">
            {faqs.map((faq, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.3, delay: 0.1 * index }}
              >
                <AccordionItem
                  value={`item-${index}`}
                  className="border-blue-900/30 bg-blue-950/10 mb-4 rounded-lg overflow-hidden"
                >
                  <AccordionTrigger className="px-6 py-4 text-white hover:text-blue-300 hover:no-underline">
                    {faq.question}
                  </AccordionTrigger>
                  <AccordionContent className="px-6 pb-4 text-blue-200">{faq.answer}</AccordionContent>
                </AccordionItem>
              </motion.div>
            ))}
          </Accordion>
        </div>

        <motion.div
          className="flex justify-center"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <div className="text-center max-w-xl">
            <p className="text-blue-200 mb-4">
              Have more questions about using cf
              <span className="relative inline-block">
                0
                <span className="absolute inset-0 flex items-center justify-center">
                  <span className="h-[2px] w-[140%] bg-white -rotate-15 transform-gpu"></span>
                </span>
              </span>{" "}
              for investment banking?
            </p>
            <Button
              className="bg-blue-600 hover:bg-blue-700 text-white animated-filled-button text-xs h-8 px-4"
              asChild
            >
              <a href="mailto:support@cf0.ai">Contact Our Financial Experts</a>
            </Button>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
