import type { NextApiRequest, NextApiResponse } from "next"
import { createSupabaseServerComponentClient } from "@/lib/supabase/server"

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" })
  }

  const { email } = req.body

  if (!email || typeof email !== "string") {
    return res.status(400).json({ error: "Email is required" })
  }

  try {
    const supabase = createSupabaseServerComponentClient()

    // Check if email already exists in waitlist
    const { data: existingEntries, error: selectError } = await supabase
      .from("waitlist")
      .select("id, status")
      .eq("email", email)
      .maybeSingle()

    if (selectError) {
      return res.status(500).json({ error: selectError.message })
    }

    if (existingEntries) {
      if (existingEntries.status === "pending") {
        return res.status(400).json({ error: "This email is already on our waitlist." })
      } else if (existingEntries.status === "approved" || existingEntries.status === "invited") {
        return res.status(400).json({ error: "This email has already been approved. Please check your inbox for the invite." })
      } else if (existingEntries.status === "converted") {
        return res.status(400).json({ error: "This email is already registered. Please sign in." })
      }
    }

    // Add email to waitlist
    const { error: insertError } = await supabase.from("waitlist").insert([{ email }])

    if (insertError) {
      return res.status(500).json({ error: insertError.message })
    }

    return res.status(200).json({ success: true })
  } catch (error) {
    console.error("Waitlist API error:", error)
    return res.status(500).json({ error: "An unexpected error occurred" })
  }
} 