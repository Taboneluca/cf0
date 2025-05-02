import { WaitlistManager } from "@/components/admin/waitlist-manager"

export const metadata = {
  title: "Waitlist Management - Admin",
  description: "Manage your waitlist entries and send invites",
}

export default function AdminWaitlistPage() {
  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">Waitlist Administration</h1>
      <div className="bg-white rounded-lg shadow-md p-6">
        <WaitlistManager />
      </div>
    </div>
  )
} 