import { NextResponse } from "next/server"
import { createRouteHandlerClient } from "@supabase/auth-helpers-nextjs"
import { cookies } from "next/headers"

export async function POST(request: Request) {
  try {
    const { title } = await request.json()

    const cookieStore = cookies()
    const supabase = createRouteHandlerClient({ cookies: () => cookieStore })

    // Verify the user is authenticated
    const { data: { session }, error: sessionError } = await supabase.auth.getSession()
    
    if (sessionError || !session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    // Generate a unique workbook ID
    const workbookWid = `wb_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // Create the new workbook
    const { data: workbook, error: workbookError } = await supabase
      .from("spreadsheet_workbooks")
      .insert({
        wid: workbookWid,
        user_id: session.user.id,
        data: {
          title: title || "Untitled Workbook",
          description: "Created with cf0"
        },
        sheets: {
          "sheet-1": {
            id: "sheet-1",
            name: "Sheet 1",
            cells: {},
            rows: 100,
            columns: 26
          }
        }
      })
      .select()
      .single()

    if (workbookError) {
      console.error("Error creating workbook:", workbookError)
      return NextResponse.json({ error: workbookError.message }, { status: 400 })
    }

    return NextResponse.json({ 
      success: true,
      workbook: workbook 
    })
  } catch (error) {
    console.error("Create workbook API error:", error)
    return NextResponse.json({ error: "An unexpected error occurred" }, { status: 500 })
  }
} 