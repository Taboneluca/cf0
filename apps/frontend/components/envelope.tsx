"use client"

import { motion } from "framer-motion"

export function Envelope() {
  return (
    <div className="relative w-64 h-64 mx-auto">
      {/* Envelope */}
      <motion.div
        className="absolute inset-0 bg-blue-900/30 rounded-lg border border-blue-500/50 shadow-lg overflow-hidden"
        initial={{ scale: 0.8, rotateY: 0 }}
        animate={{
          scale: 1,
          rotateY: [0, 10, -10, 10, -10, 0],
          transition: {
            scale: { duration: 0.5 },
            rotateY: { delay: 1.5, duration: 1.5 },
          },
        }}
      >
        {/* Envelope body */}
        <div className="absolute inset-0 bg-gradient-to-br from-blue-900/80 to-blue-950/80 rounded-lg"></div>

        {/* Envelope flap */}
        <motion.div
          className="absolute top-0 left-0 w-full h-1/2 origin-bottom"
          initial={{ rotateX: 0 }}
          animate={{
            rotateX: [0, -180, -180, 0],
            transition: {
              times: [0, 0.3, 0.7, 1],
              duration: 3,
              ease: "easeInOut",
            },
          }}
        >
          <div className="absolute bottom-0 left-0 w-full h-full bg-blue-800/50 rounded-t-lg origin-bottom transform-gpu">
            <div className="absolute bottom-0 left-0 w-full h-full bg-gradient-to-t from-blue-900/0 to-blue-700/50"></div>
          </div>
        </motion.div>

        {/* Envelope bottom fold */}
        <div className="absolute bottom-0 left-0 w-full h-1/2 bg-blue-800/30 rounded-b-lg">
          <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-b from-blue-900/0 to-blue-700/30"></div>
        </div>

        {/* Letter */}
        <motion.div
          className="absolute top-1/2 left-1/2 w-[90%] h-[85%] bg-blue-100/90 rounded-md -translate-x-1/2 -translate-y-1/2"
          initial={{ y: 0 }}
          animate={{
            y: [-10, -40, -40, -10],
            transition: {
              times: [0, 0.3, 0.7, 1],
              duration: 3,
              ease: "easeInOut",
            },
          }}
        >
          {/* Letter content */}
          <div className="absolute inset-0 p-4 flex flex-col items-center justify-center">
            <div className="w-full h-3 bg-blue-400/40 rounded-full mb-3"></div>
            <div className="w-full h-3 bg-blue-400/40 rounded-full mb-3"></div>
            <div className="w-3/4 h-3 bg-blue-400/40 rounded-full mb-6"></div>
            <div className="w-12 h-12 rounded-full bg-blue-500/30 flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-blue-600"
              >
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div>
          </div>
        </motion.div>

        {/* Envelope shine effect */}
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-400/10 to-transparent"
          initial={{ x: -200, opacity: 0 }}
          animate={{
            x: [200, -200],
            opacity: [0, 0.5, 0],
            transition: {
              repeat: Number.POSITIVE_INFINITY,
              repeatDelay: 2,
              duration: 1.5,
            },
          }}
        ></motion.div>
      </motion.div>

      {/* Envelope shadow */}
      <motion.div
        className="absolute -bottom-4 left-1/2 w-[90%] h-6 bg-blue-500/20 rounded-full blur-md -translate-x-1/2"
        initial={{ scale: 0.8, opacity: 0.3 }}
        animate={{
          scale: [0.8, 1, 0.8],
          opacity: [0.3, 0.5, 0.3],
          transition: {
            repeat: Number.POSITIVE_INFINITY,
            duration: 2,
          },
        }}
      ></motion.div>

      {/* Particles */}
      {[...Array(6)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute top-1/2 left-1/2 w-2 h-2 rounded-full bg-blue-400"
          initial={{
            x: 0,
            y: 0,
            scale: 0,
            opacity: 0,
          }}
          animate={{
            x: [0, (Math.random() - 0.5) * 150],
            y: [0, (Math.random() - 0.5) * 150],
            scale: [0, 1, 0],
            opacity: [0, 1, 0],
            transition: {
              delay: 1.5 + i * 0.1,
              duration: 1 + Math.random(),
              ease: "easeOut",
            },
          }}
        ></motion.div>
      ))}
    </div>
  )
}
