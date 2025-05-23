import type React from "react"
import type { Metadata } from "next"
import { Inter } from "next/font/google"
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
      { url: '/new-logo.png', sizes: '32x32', type: 'image/png' },
      { url: '/new-logo.png', sizes: '16x16', type: 'image/png' },
    ],
    shortcut: '/new-logo.png',
    apple: [
      { url: '/new-logo.png', sizes: '180x180', type: 'image/png' },
    ],
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-inter">{children}</body>
    </html>
  )
}
