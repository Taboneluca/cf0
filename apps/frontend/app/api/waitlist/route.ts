import { NextResponse } from "next/server"
import { createClient } from '@supabase/supabase-js'

export async function POST(request: Request) {
  try {
    const { email, name, company } = await request.json()

    if (!email || typeof email !== "string") {
      return NextResponse.json({ error: "Email is required" }, { status: 400 })
    }

    // Create Supabase client
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    
    if (!supabaseUrl || !supabaseKey) {
      return NextResponse.json({ error: "Missing Supabase configuration" }, { status: 500 })
    }
    
    const supabase = createClient(supabaseUrl, supabaseKey)

    // Check if email already exists in waitlist
    const { data: existingEntries, error: selectError } = await supabase
      .from("waitlist")
      .select("id, status")
      .eq("email", email)
      .maybeSingle()

    if (selectError) {
      return NextResponse.json({ error: selectError.message }, { status: 500 })
    }

    if (existingEntries) {
      if (existingEntries.status === "pending") {
        return NextResponse.json({ error: "This email is already on our waitlist." }, { status: 400 })
      } else if (existingEntries.status === "approved" || existingEntries.status === "invited") {
        return NextResponse.json({ error: "This email has already been approved. Please check your inbox for the invite." }, { status: 400 })
      } else if (existingEntries.status === "converted") {
        return NextResponse.json({ error: "This email is already registered. Please sign in." }, { status: 400 })
      }
    }

    // Add email to waitlist
    const { error: insertError } = await supabase.from("waitlist").insert([{ 
      email,
      status: "pending"
    }])

    if (insertError) {
      return NextResponse.json({ error: insertError.message }, { status: 500 })
    }

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error("Waitlist API error:", error)
    return NextResponse.json({ error: "An unexpected error occurred" }, { status: 500 })
  }
} 