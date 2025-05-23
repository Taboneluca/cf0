import { backendSheetToUI } from "./transform"

// Utility to proxy chat requests to the FastAPI backend
export async function chatBackend(
  mode: "ask" | "analyst",
  message: string,
  wid: string,
  sid: string,
  contexts: string[] = [],
  model?: string
) {
  console.log(`📝 Chat request: mode=${mode}, wid=${wid}, sid=${sid}, contexts=${contexts.length}`);
  
  try {
    console.log(`⏳ Sending request to ${process.env.NEXT_PUBLIC_BACKEND_URL}/chat`);
    
    const startTime = performance.now();
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/chat`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, message, wid, sid, contexts, model }),
      }
    );
    const requestTime = performance.now() - startTime;
    console.log(`⏱️ API request completed in ${requestTime.toFixed(0)}ms with status ${res.status}`);
    
    // Handle different types of errors with better user feedback
    if (!res.ok) {
      let errorData;
      let errorMessage = `API request failed with status ${res.status}`;
      
      try {
        // Try to parse response as JSON for structured error info
        errorData = await res.json();
        console.error(`🔴 API Error Response (${res.status}):`, errorData);
        
        // Handle specific error types with custom messages
        if (res.status === 422 || res.status === 500) {
          if (errorData?.detail?.includes("Cannot parse JSON")) {
            // JSON parsing error - common with LLM response issues
            return {
              reply: "Sorry, I encountered an error processing your request. Please try again with simpler instructions.",
              sheet: null,
              all_sheets: {},
              log: [],
              error: true,
              errorDetail: errorData.detail
            };
          }
        }
        
        // Use structured error message if available
        errorMessage = errorData?.detail || errorMessage;
      } catch (parseError) {
        // If JSON parsing of error fails, try plain text
        try {
          const errorText = await res.text();
          console.error(`🔴 API Error Response (${res.status}):`, errorText);
          errorMessage = errorText || errorMessage;
        } catch {
          // If even text extraction fails, use generic message
          console.error(`🔴 API Error Response (${res.status}): Could not parse response`);
        }
      }
      
      // For really bad errors (500s), return a friendly error structure instead of throwing
      if (res.status >= 500) {
        return {
          reply: `Sorry, the server encountered an error. Please try again in a moment.`,
          sheet: null,
          all_sheets: {},
          log: [],
          error: true,
          errorDetail: errorMessage
        };
      }
      
      throw new Error(`API Error (${res.status}): ${errorMessage}`);
    }
    
    const data = await res.json();
    
    // Log response structure (without full cell data)
    console.log(`✅ API Response Structure:`, {
      hasReply: !!data?.reply,
      hasSheet: !!data?.sheet,
      hasAllSheets: !!data?.all_sheets,
      hasLog: !!data?.log,
      replyLength: data?.reply?.length,
      sheetName: data?.sheet?.name,
      cellCount: data?.sheet?.cells?.length,
    });
    
    // Validate response shape
    if (!data || !data.reply || !data.sheet) {
      console.error("🔴 Invalid API response format:", data);
      
      // Return error response instead of throwing
      return {
        reply: "Sorry, I received an incomplete response. Please try again.",
        sheet: null,
        all_sheets: {},
        log: [],
        error: true,
        errorDetail: "Invalid API response format: missing required fields"
      };
    }
    
    return data as { 
      reply: string; 
      sheet: any;
      all_sheets: Record<string, any>; 
      log: { cell: string; old_value: any; new: any }[] 
    };
  } catch (err) {
    console.error("🔴 chatBackend error:", err);
    
    // Return graceful error instead of throwing
    return {
      reply: "Sorry, I encountered an error connecting to the server. Please try again.",
      sheet: null,
      all_sheets: {},
      log: [],
      error: true,
      errorDetail: err instanceof Error ? err.message : String(err)
    };
  }
}

export async function fetchSheet(wid: string, sid: string) {
  try {
    const r = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/workbook/${wid}/sheet/${sid}`)
    
    if (!r.ok) {
      const errorText = await r.text();
      throw new Error(`API Error (${r.status}): ${errorText}`);
    }
    
    const data = await r.json();
    
    if (!data || !data.sheet) {
      throw new Error("Invalid API response format: missing 'sheet' field");
    }
    
    return backendSheetToUI(data.sheet)
  } catch (err) {
    console.error("fetchSheet error:", err);
    throw err;
  }
}

export async function createSheet(wid: string, name?: string) {
  try {
    const r = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/workbook/${wid}/sheet`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: name ? JSON.stringify({ name }) : JSON.stringify({})
    })
    
    if (!r.ok) {
      const errorText = await r.text();
      throw new Error(`API Error (${r.status}): ${errorText}`);
    }
    
    const data = await r.json();
    
    if (!data || !data.sheet) {
      throw new Error("Invalid API response format: missing required fields");
    }
    
    return data as { sheets: string[]; active: string; sheet: any }
  } catch (err) {
    console.error("createSheet error:", err);
    throw err;
  }
} 