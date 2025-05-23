import { WaitlistManager } from "@/components/admin/waitlist-manager"

export const metadata = {
  title: "Waitlist Management - Admin",
  description: "Manage your waitlist entries and send invites",
}

export default function AdminWaitlistPage() {
  return (
    <div className="min-h-screen bg-black">
      <div className="container max-w-6xl mx-auto py-8 px-4">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Waitlist Administration</h1>
          <p className="text-blue-200">Manage waitlist entries and send invitations</p>
        </div>
        <div className="bg-blue-950/20 rounded-lg border border-blue-900/30 p-6">
          <WaitlistManager />
        </div>
      </div>
    </div>
  )
} 