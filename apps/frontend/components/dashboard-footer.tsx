import Link from "next/link"
import { Logo } from "./logo"

export function DashboardFooter() {
  return (
    <footer className="w-full border-t border-blue-900/30 bg-black py-4">
      <div className="container px-4 md:px-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Logo size="sm" />
            <span className="text-xs text-blue-400">&copy; {new Date().getFullYear()} All rights reserved.</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-blue-400">
            <Link href="/privacy" className="hover:text-blue-300">
              Privacy
            </Link>
            <Link href="/terms" className="hover:text-blue-300">
              Terms
            </Link>
            <Link href="/support" className="hover:text-blue-300">
              Support
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}
