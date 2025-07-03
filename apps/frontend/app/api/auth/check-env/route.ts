import { NextResponse } from "next/server"

export async function GET() {
  try {
    const envVars = {
      NEXT_PUBLIC_SUPABASE_URL: !!process.env.NEXT_PUBLIC_SUPABASE_URL,
      NEXT_PUBLIC_SUPABASE_ANON_KEY: !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
      SUPABASE_SERVICE_ROLE_KEY: !!process.env.SUPABASE_SERVICE_ROLE_KEY,
      NEXT_PUBLIC_SITE_URL: !!process.env.NEXT_PUBLIC_SITE_URL,
      NODE_ENV: process.env.NODE_ENV,
    }

    const missingVars = Object.entries(envVars).filter(([key, value]) => !value && key !== 'NODE_ENV').map(([key]) => key)

    return NextResponse.json({
      environment: process.env.NODE_ENV,
      allRequiredPresent: missingVars.length === 0,
      missing: missingVars,
      present: envVars,
      siteUrl: process.env.NEXT_PUBLIC_SITE_URL,
      timestamp: new Date().toISOString()
    })
  } catch (error) {
    console.error("Environment check error:", error)
    return NextResponse.json({ error: "Failed to check environment" }, { status: 500 })
  }
} 