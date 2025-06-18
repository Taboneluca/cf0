import type React from "react"
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import { ModelProvider } from "@/context/ModelContext"
import "./globals.css"

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
})

export const metadata: Metadata = {
  title: "cf0 - Spreadsheets Powered by AI",
  description:
    "cf0 combines the power of spreadsheets with AI to help you analyze and manipulate your data more efficiently.",
  generator: 'v0.dev',
  icons: {
    icon: [
      { url: '/transparent_image_v2.png?v=1', sizes: '64x64', type: 'image/png' },
      { url: '/transparent_image_v2.png?v=1', sizes: '32x32', type: 'image/png' },
      { url: '/transparent_image_v2.png?v=1', sizes: '16x16', type: 'image/png' },
    ],
    shortcut: '/transparent_image_v2.png?v=1',
    apple: [
      { url: '/transparent_image_v2.png?v=1', sizes: '180x180', type: 'image/png' },
    ],
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // Add debug environment variables for development
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  (window as any).DEBUG_STREAMING = true;
  (window as any).DEBUG_SSE = true;
  process.env.NEXT_PUBLIC_DEBUG_STREAMING = '1';
  process.env.NEXT_PUBLIC_DEBUG_SSE = '1';
}

  return (
    <html lang="en" className={inter.variable}>
      <body className="font-inter">
        <ModelProvider>
          {children}
        </ModelProvider>
      </body>
    </html>
  )
}
