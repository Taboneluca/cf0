export interface Profile {
  id: string
  email: string
  full_name: string | null
  avatar_url: string | null
  is_waitlisted: boolean
  is_verified: boolean
  created_at: string
  updated_at: string
}

export interface Workbook {
  id: string
  user_id: string
  title: string
  description: string | null
  data: any
  is_public: boolean
  created_at: string
  updated_at: string
}

export interface WaitlistEntry {
  id: string
  email: string
  status: "pending" | "approved" | "rejected" | "converted"
  invite_code: string | null
  invited_at: string | null
  created_at: string
}
