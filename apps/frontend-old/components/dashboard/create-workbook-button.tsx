"use client"

import type React from "react"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { supabase, getCurrentUserId } from "@/lib/supabase/client"

interface CreateWorkbookButtonProps {
  userId: string
}

export function CreateWorkbookButton({ userId }: CreateWorkbookButtonProps) {
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [isPublic, setIsPublic] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [authVerified, setAuthVerified] = useState(false)
  const router = useRouter()
  
  // Verify user session is active when component loads
  useEffect(() => {
    const checkSession = async () => {
      try {
        const currentUserId = await getCurrentUserId();
        console.log("Workbook component auth check:", {
          propUserId: userId,
          currentUserId: currentUserId,
          hasValidSession: !!currentUserId
        });
        
        setAuthVerified(!!currentUserId);
        
        // If no currentUserId at this point, force a new login
        if (!currentUserId) {
          const { error } = await supabase.auth.refreshSession();
          if (error) {
            console.log("Session refresh failed, redirecting to login");
            router.push('/login');
          }
        }
      } catch (error) {
        console.error("Session check failed:", error);
      }
    }
    
    checkSession();
  }, [userId, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      // Get current authenticated user ID
      const authUserId = await getCurrentUserId();
      
      if (!authUserId) {
        alert("Your session has expired. Please sign in again.");
        router.push('/login');
        return;
      }
      
      console.log("Creating workbook with auth user:", authUserId);
        
      // Generate a random UUID for the new workbook
      const newWorkbookId = crypto.randomUUID();
      
      // Use a direct SQL function for more reliability
      const { data, error } = await supabase.rpc(
        'admin_insert_workbook',
        {
          workbook_id: newWorkbookId,
          owner_id: authUserId,
          workbook_title: title,
          workbook_description: description,
          is_public: isPublic
        }
      )

      if (error) {
        console.error("RPC function error:", error);
        throw error;
      }

      // Navigate to the new workbook
      console.log("Workbook created successfully, navigating to:", newWorkbookId);
      router.push(`/workbook/${newWorkbookId}`);
      router.refresh();
    } catch (error) {
      console.error("Error creating workbook:", error);
      alert("Failed to create workbook. Please try again.");
    } finally {
      setIsLoading(false);
      setIsModalOpen(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        className="rounded-md bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
        disabled={!authVerified}
      >
        Create Workbook
      </button>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6">
            <h2 className="mb-4 text-xl font-bold">Create New Workbook</h2>
            {!authVerified ? (
              <div className="text-red-500 mb-4">
                Authentication error. Please refresh the page or sign in again.
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="title" className="block text-sm font-medium text-gray-700">
                    Title
                  </label>
                  <input
                    id="title"
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                    Description (optional)
                  </label>
                  <textarea
                    id="description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={3}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-blue-500"
                  />
                </div>
                <div className="flex items-center">
                  <input
                    id="is-public"
                    type="checkbox"
                    checked={isPublic}
                    onChange={(e) => setIsPublic(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <label htmlFor="is-public" className="ml-2 block text-sm text-gray-700">
                    Make this workbook public
                  </label>
                </div>
                <div className="flex justify-end space-x-2">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="rounded-md bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50"
                  >
                    {isLoading ? "Creating..." : "Create"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  )
}
