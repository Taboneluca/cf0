import type { Metadata } from 'next'
import './globals.css'
import { ModelProvider } from '@/context/ModelContext'
import { Toaster } from 'react-hot-toast'

export const metadata: Metadata = {
  title: 'Intelligent Spreadsheet',
  description: 'Intelligent Spreadsheet with AI Assistant',
  generator: 'v0.dev',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>
        <ModelProvider>
          {children}
          <Toaster position="bottom-right" />
        </ModelProvider>
      </body>
    </html>
  )
}
