import Link from "next/link"
import { Logo } from "./logo"

export function Footer() {
  return (
    <footer className="w-full border-t border-blue-900/30 bg-black py-12">
      <div className="container px-4 md:px-6">
        <div className="grid gap-8 sm:grid-cols-2 md:grid-cols-4">
          <div className="space-y-4">
            <Logo clickable={true} />
            <p className="text-sm text-blue-200">
              Spreadsheets powered by AI. Analyze and manipulate your data more efficiently.
            </p>
          </div>
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-white">Navigation</h4>
            <nav className="flex flex-col space-y-2 text-sm">
              <Link href="#features" className="text-blue-300 hover:text-blue-100">
                Features
              </Link>
              <Link href="#how-it-works" className="text-blue-300 hover:text-blue-100">
                How It Works
              </Link>
              <Link href="#pricing" className="text-blue-300 hover:text-blue-100">
                Pricing
              </Link>
              <Link href="#faq" className="text-blue-300 hover:text-blue-100">
                FAQ
              </Link>
            </nav>
          </div>
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-white">Resources</h4>
            <nav className="flex flex-col space-y-2 text-sm">
              <Link href="/blog" className="text-blue-300 hover:text-blue-100">
                Blog
              </Link>
              <Link href="/support" className="text-blue-300 hover:text-blue-100">
                Support
              </Link>
              <Link href="/documentation" className="text-blue-300 hover:text-blue-100">
                Documentation
              </Link>
              <Link href="/changelog" className="text-blue-300 hover:text-blue-100">
                Changelog
              </Link>
            </nav>
          </div>
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-white">Legal</h4>
            <nav className="flex flex-col space-y-2 text-sm">
              <Link href="/privacy" className="text-blue-300 hover:text-blue-100">
                Privacy Policy
              </Link>
              <Link href="/terms" className="text-blue-300 hover:text-blue-100">
                Terms of Service
              </Link>
              <Link href="/cookies" className="text-blue-300 hover:text-blue-100">
                Cookie Policy
              </Link>
            </nav>
          </div>
        </div>
        <div className="mt-8 flex flex-col items-center justify-between gap-4 border-t border-blue-900/30 pt-8 sm:flex-row">
          <p className="text-xs text-blue-400">
            &copy; {new Date().getFullYear()} cf
            <span className="relative inline-block">
              0
              <span className="absolute inset-0 flex items-center justify-center">
                <span className="h-[1px] w-[140%] bg-blue-400 -rotate-15 transform-gpu"></span>
              </span>
            </span>
            .ai. All rights reserved.
          </p>
          <div className="flex items-center gap-4">
            <Link href="#" className="text-blue-400 hover:text-blue-300">
              <span className="sr-only">Twitter</span>
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
                className="h-5 w-5"
              >
                <path d="M22 4s-.7 2.1-2 3.4c1.6 10-9.4 17.3-18 11.6 2.2.1 4.4-.6 6-2C3 15.5.5 9.6 3 5c2.2 2.6 5.6 4.1 9 4-.9-4.2 4-6.6 7-3.8 1.1 0 3-1.2 3-1.2z" />
              </svg>
            </Link>
            <Link href="#" className="text-blue-400 hover:text-blue-300">
              <span className="sr-only">GitHub</span>
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
                className="h-5 w-5"
              >
                <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
                <path d="M9 18c-4.51 2-5-2-7-2" />
              </svg>
            </Link>
            <Link href="#" className="text-blue-400 hover:text-blue-300">
              <span className="sr-only">LinkedIn</span>
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
                className="h-5 w-5"
              >
                <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
                <rect width="4" height="12" x="2" y="9" />
                <circle cx="4" cy="4" r="2" />
              </svg>
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
