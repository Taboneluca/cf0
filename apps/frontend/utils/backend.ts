import { backendSheetToUI } from "./transform"

// Utility to proxy chat requests to the FastAPI backend
export async function chatBackend(
  mode: "ask" | "analyst",
  message: string,
  wid: string,
  sid: string
) {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/chat`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, message, wid, sid }),
      }
    );
    
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`API Error (${res.status}): ${errorText}`);
    }
    
    const data = await res.json();
    
    // Validate response shape
    if (!data || !data.reply || !data.sheet) {
      throw new Error("Invalid API response format: missing required fields");
    }
    
    return data as { 
      reply: string; 
      sheet: any;
      all_sheets: Record<string, any>; 
      log: { cell: string; old_value: any; new: any }[] 
    };
  } catch (err) {
    console.error("chatBackend error:", err);
    throw err;
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
