"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { Header } from "@/components/header"
import { DashboardFooter } from "@/components/dashboard-footer"
import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PlusCircle, FileSpreadsheet, Upload, Download, Clock, Calendar, MoreHorizontal, Settings, Users } from "lucide-react"
import { motion } from "framer-motion"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { supabase } from "@/lib/supabase/client"

// Sample data for workbooks - now empty for new users
const createdWorkbooks: Array<{
  id: number
  name: string
  createdAt: string
  updatedAt: string
  color: string
}> = []

const importedWorkbooks: Array<{
  id: number
  name: string
  createdAt: string
  updatedAt: string
  color: string
}> = []

// Helper function to format dates
const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date)
}

export default function Dashboard() {
  const router = useRouter()
  const [workbooks, setWorkbooks] = useState({
    created: [...createdWorkbooks],
    imported: [...importedWorkbooks],
  })
  const [isRenaming, setIsRenaming] = useState<{ id: number; type: "created" | "imported" } | null>(null)
  const [newName, setNewName] = useState("")
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<{ id: number; type: "created" | "imported" } | null>(null)
  const [activeTab, setActiveTab] = useState("all")
  const [isAdmin, setIsAdmin] = useState(false)
  const [isLoadingAdmin, setIsLoadingAdmin] = useState(true)
  const [isCreatingWorkbook, setIsCreatingWorkbook] = useState(false)

  // Check if user is admin
  useEffect(() => {
    const checkAdminStatus = async () => {
      try {
        console.log("Checking admin status...")
        
        // Use the debug endpoint (same method as manual test that works)
        const response = await fetch('/api/debug/admin-check', {
          credentials: 'include',
          cache: 'no-cache'
        })
        
        if (!response.ok) {
          console.error("Admin check failed with status:", response.status)
          setIsAdmin(false)
          return
        }
        
        const data = await response.json()
        
        if (data.isAdmin !== undefined) {
          setIsAdmin(data.isAdmin)
          console.log("Admin status:", data.isAdmin ? "✅ Admin" : "❌ Regular user")
        } else {
          console.warn("Admin check didn't return admin status")
          setIsAdmin(false)
        }
        
      } catch (error) {
        console.error("Admin check failed:", error)
        setIsAdmin(false)
      } finally {
        setIsLoadingAdmin(false)
      }
    }

    // Add a small delay to let auth stabilize first
    const timeoutId = setTimeout(() => {
      checkAdminStatus()
    }, 300) // 300ms delay - fast but still allows auth to stabilize
    
    return () => clearTimeout(timeoutId)
  }, [])

  // Create new workbook function
  const createNewWorkbook = async () => {
    setIsCreatingWorkbook(true)
    try {
      const response = await fetch("/api/workbooks/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          title: `Workbook ${new Date().toLocaleDateString()}`,
          description: "Created with cf0" 
        }),
      })
      
      const result = await response.json()
      
      if (!response.ok) {
        throw new Error(result.error || "Failed to create workbook")
      }
      
      // Redirect to the new workbook
      router.push(`/workbook/${result.workbook.id}`)
    } catch (error: any) {
      console.error("Error creating workbook:", error)
      alert("Failed to create workbook. Please try again.")
    } finally {
      setIsCreatingWorkbook(false)
    }
  }

  const handleDelete = (id: number, type: "created" | "imported") => {
    setWorkbooks((prev) => ({
      ...prev,
      [type]: prev[type].filter((workbook) => workbook.id !== id),
    }))
    setShowDeleteConfirm(null)
  }

  const handleRename = (id: number, type: "created" | "imported") => {
    if (newName.trim()) {
      setWorkbooks((prev) => ({
        ...prev,
        [type]: prev[type].map((workbook) => (workbook.id === id ? { ...workbook, name: newName } : workbook)),
      }))
      setIsRenaming(null)
      setNewName("")
    }
  }

  const startRenaming = (workbook: (typeof createdWorkbooks)[0], type: "created" | "imported") => {
    setIsRenaming({ id: workbook.id, type })
    setNewName(workbook.name)
  }

  // Workbook card component
  function WorkbookCard({
    workbook,
    type,
  }: {
    workbook: (typeof createdWorkbooks)[0]
    type: "created" | "imported"
  }) {
    // Updated color scheme: blue glow for created, green for imported
    const colorMap = {
      created: "bg-blue-500/20 border-blue-500/50 text-blue-400 shadow-lg shadow-blue-500/20",
      imported: "bg-emerald-500/20 border-emerald-500/50 text-emerald-400 shadow-lg shadow-emerald-500/20",
    }

    const colorClass = colorMap[type]

    return (
      <motion.div
        className={`workbook-card rounded-lg border ${colorClass} bg-black/40 p-4 backdrop-blur-sm hover:shadow-xl transition-all duration-300`}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        whileHover={{ scale: 1.02, y: -5 }}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`flex h-10 w-10 items-center justify-center rounded-md ${colorClass}`}>
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div>
              {isRenaming && isRenaming.id === workbook.id && isRenaming.type === type ? (
                <div className="flex items-center gap-2">
                  <Input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    className="h-7 bg-blue-950/50 border-blue-900/50 text-white"
                    autoFocus
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        handleRename(workbook.id, type)
                      } else if (e.key === "Escape") {
                        setIsRenaming(null)
                        setNewName("")
                      }
                    }}
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2 text-blue-300 hover:text-blue-100 animated-button text-xs"
                    onClick={() => handleRename(workbook.id, type)}
                  >
                    Save
                  </Button>
                </div>
              ) : (
                <h3 className="font-medium text-white">{workbook.name}</h3>
              )}
              <div className="flex items-center gap-3 text-xs text-blue-200">
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  {formatDate(workbook.createdAt)}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDate(workbook.updatedAt)}
                </span>
              </div>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8 text-blue-300 hover:text-blue-100 animated-button">
                <MoreHorizontal className="h-4 w-4" />
                <span className="sr-only">More options</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-blue-950 border-blue-900 text-blue-100">
              <DropdownMenuItem
                className="hover:bg-blue-900 hover:text-blue-50 cursor-pointer"
                onClick={() => startRenaming(workbook, type)}
              >
                Rename
              </DropdownMenuItem>
              <DropdownMenuItem className="hover:bg-blue-900 hover:text-blue-50 cursor-pointer">
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuItem
                className="hover:bg-blue-900 hover:text-blue-50 cursor-pointer text-red-400 hover:text-red-300"
                onClick={() => setShowDeleteConfirm({ id: workbook.id, type })}
              >
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            variant="outline"
            size="sm"
            className="text-xs border-blue-500/50 text-blue-400 hover:bg-blue-950 animated-button"
          >
            <Download className="mr-1 h-3 w-3" />
            Export to Excel
          </Button>
        </div>

        {/* Delete confirmation dialog */}
        {showDeleteConfirm && showDeleteConfirm.id === workbook.id && showDeleteConfirm.type === type && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-blue-950 border border-blue-900 rounded-lg p-6 max-w-md w-full mx-4">
              <h3 className="text-xl font-bold text-white mb-2">Delete Workbook</h3>
              <p className="text-blue-200 mb-6">
                Are you sure you want to delete "{workbook.name}"? This action cannot be undone.
              </p>
              <div className="flex justify-end gap-3">
                <Button
                  variant="outline"
                  className="border-blue-700 text-blue-300 hover:bg-blue-900 animated-button text-xs h-8"
                  onClick={() => setShowDeleteConfirm(null)}
                >
                  Cancel
                </Button>
                <Button
                  className="bg-red-600 hover:bg-red-700 text-white animated-filled-button text-xs h-8"
                  onClick={() => handleDelete(workbook.id, type)}
                >
                  Delete
                </Button>
              </div>
            </div>
          </div>
        )}
      </motion.div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col bg-black">
      <Header />
      <main className="flex-1">
        <div className="container py-8 px-4 md:px-6">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-white mb-2">Your Workbooks</h1>
            <p className="text-blue-200">Manage and organize all your spreadsheets in one place.</p>
          </div>

          {/* Admin Section */}
          {isAdmin && !isLoadingAdmin && (
            <motion.div
              className="mb-8 rounded-lg border border-orange-500/30 bg-orange-500/10 p-6"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-orange-500/20 border border-orange-500/30">
                    <Settings className="h-5 w-5 text-orange-400" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-white">Admin Panel</h2>
                    <p className="text-orange-200 text-sm">Manage waitlist and system settings</p>
                  </div>
                </div>
                <Button
                  asChild
                  className="bg-orange-600 hover:bg-orange-700 text-white animated-filled-button text-xs h-8"
                >
                  <Link href="/admin/waitlist">
                    <Users className="mr-2 h-3 w-3" />
                    Manage Waitlist
                  </Link>
                </Button>
              </div>
            </motion.div>
          )}

          <div className="mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <Tabs defaultValue="all" className="w-full sm:w-auto" onValueChange={setActiveTab}>
              <TabsList className="bg-blue-950/50 border border-blue-900/50">
                <TabsTrigger value="all" className="data-[state=active]:bg-blue-900 data-[state=active]:text-white">
                  All
                </TabsTrigger>
                <TabsTrigger value="created" className="data-[state=active]:bg-blue-900 data-[state=active]:text-white">
                  Created
                </TabsTrigger>
                <TabsTrigger
                  value="imported"
                  className="data-[state=active]:bg-blue-900 data-[state=active]:text-white"
                >
                  Imported
                </TabsTrigger>
              </TabsList>
            </Tabs>

            <div className="flex gap-2 w-full sm:w-auto">
              <Button 
                className="bg-blue-600 hover:bg-blue-700 text-white animated-filled-button text-xs h-8"
                onClick={createNewWorkbook}
                disabled={isCreatingWorkbook}
              >
                <PlusCircle className="mr-1 h-3 w-3" />
                {isCreatingWorkbook ? "Creating..." : "Create New Workbook"}
              </Button>
              <Button
                variant="outline"
                className="border-blue-600 text-blue-400 hover:bg-blue-950 animated-button text-xs h-8"
              >
                <Upload className="mr-1 h-3 w-3" />
                Import
              </Button>
            </div>
          </div>

          <div className="space-y-8">
            {(activeTab === "all" || activeTab === "created") && (
              <div>
                <h2 className="text-xl font-semibold text-white mb-4">Workbooks Created on Website</h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {workbooks.created.map((workbook) => (
                    <WorkbookCard key={workbook.id} workbook={workbook} type="created" />
                  ))}
                </div>
              </div>
            )}

            {(activeTab === "all" || activeTab === "imported") && (
              <div>
                <h2 className="text-xl font-semibold text-white mb-4">Imported Workbooks</h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {workbooks.imported.map((workbook) => (
                    <WorkbookCard key={workbook.id} workbook={workbook} type="imported" />
                  ))}
                </div>
              </div>
            )}

            {activeTab === "all" && workbooks.created.length === 0 && workbooks.imported.length === 0 && (
              <div className="text-center py-12">
                <div className="inline-flex h-20 w-20 items-center justify-center rounded-full bg-blue-900/20 mb-4">
                  <FileSpreadsheet className="h-10 w-10 text-blue-400" />
                </div>
                <h3 className="text-xl font-medium text-white mb-2">No workbooks yet</h3>
                <p className="text-blue-200 mb-6 max-w-md mx-auto">
                  Create your first workbook or import an existing spreadsheet to get started.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <Button 
                    className="bg-blue-600 hover:bg-blue-700 text-white animated-filled-button text-xs h-8"
                    onClick={createNewWorkbook}
                    disabled={isCreatingWorkbook}
                  >
                    <PlusCircle className="mr-2 h-3 w-3" />
                    {isCreatingWorkbook ? "Creating..." : "Create New Workbook"}
                  </Button>
                  <Button
                    variant="outline"
                    className="border-blue-600 text-blue-400 hover:bg-blue-950 animated-button text-xs h-8"
                  >
                    <Upload className="mr-2 h-3 w-3" />
                    Import Spreadsheet
                  </Button>
                </div>
              </div>
            )}

            {activeTab === "created" && workbooks.created.length === 0 && (
              <div className="text-center py-12">
                <p className="text-blue-200">No created workbooks found. Create your first workbook to get started.</p>
              </div>
            )}

            {activeTab === "imported" && workbooks.imported.length === 0 && (
              <div className="text-center py-12">
                <p className="text-blue-200">No imported workbooks found. Import a spreadsheet to get started.</p>
              </div>
            )}
          </div>
        </div>
      </main>
      <DashboardFooter />
    </div>
  )
}
