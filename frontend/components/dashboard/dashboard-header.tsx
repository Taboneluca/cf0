"use client"

import Link from "next/link"
import type { User } from "@supabase/supabase-js"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { supabase } from "@/lib/supabase/client"

interface DashboardHeaderProps {
  user: User
  isAdmin?: boolean
}

export function DashboardHeader({ user, isAdmin = false }: DashboardHeaderProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const router = useRouter()

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push("/")
    router.refresh()
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-white">
      <div className="container flex h-14 items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="font-bold">
            CF0
          </Link>
          
          <nav className="ml-6 hidden md:flex">
            <Link 
              href="/dashboard" 
              className="mx-2 text-sm font-medium text-gray-600 hover:text-gray-900"
            >
              Workbooks
            </Link>
            {isAdmin && (
              <Link 
                href="/admin/waitlist" 
                className="mx-2 text-sm font-medium text-blue-600 hover:text-blue-800"
              >
                Waitlist Admin
              </Link>
            )}
          </nav>
        </div>
        <div className="relative">
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="flex items-center gap-2 rounded-full bg-gray-100 p-1 text-sm font-medium"
          >
            <span className="ml-2">{user.email}</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-500 text-white">
              {user.email?.charAt(0).toUpperCase() || "U"}
            </div>
          </button>
          {isMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 rounded-md bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5">
              <Link
                href="/profile"
                className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                onClick={() => setIsMenuOpen(false)}
              >
                Profile
              </Link>
              {isAdmin && (
                <Link
                  href="/admin/waitlist"
                  className="block px-4 py-2 text-sm text-blue-600 hover:bg-gray-100"
                  onClick={() => setIsMenuOpen(false)}
                >
                  Waitlist Admin
                </Link>
              )}
              <button
                onClick={handleSignOut}
                className="block w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
