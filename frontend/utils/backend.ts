import { backendSheetToUI } from "./transform"

// Utility to proxy chat requests to the FastAPI backend
export async function chatBackend(
  mode: "ask" | "analyst",
  message: string,
  wid: string,
  sid: string
) {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_BACKEND_URL}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, message, wid, sid }),
    }
  );
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as { 
    reply: string; 
    sheet: any; 
    log: { cell: string; old_value: any; new: any }[] 
  };
}

export async function fetchSheet(wid: string, sid: string) {
  const r = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/workbook/${wid}/sheet/${sid}`)
  if (!r.ok) throw new Error(await r.text())
  const { sheet } = await r.json()
  return backendSheetToUI(sheet)
}

export async function createSheet(wid: string, name?: string) {
  const r = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/workbook/${wid}/sheet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: name ? JSON.stringify({ name }) : JSON.stringify({})
  })
  if (!r.ok) throw new Error(await r.text())
  return await r.json() as { sheets: string[]; active: string; sheet: any }
}
