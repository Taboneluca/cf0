import { Plus } from "lucide-react"
import { useWorkbook } from "@/context/workbook-context"
import { fetchSheet, createSheet } from "@/utils/backend"
import { backendSheetToUI } from "@/utils/transform"
import { supabase } from "@/lib/supabase/client"

export default function SheetTabs() {
  const [wb, dispatch] = useWorkbook()
  const { wid, sheets, active } = wb

  const switchTo = async (sid: string, forFormula = false) => {
    if (wb.data[sid]) { 
      dispatch({ type: "SWITCH", sid })
      return 
    }
    try {
      const sheet = await fetchSheet(wid, sid)
      dispatch({ type: "UPDATE_SHEET", sid, data: sheet })
      dispatch({ type: "SWITCH", sid })
    } catch (error) {
      console.error("Error fetching sheet:", error)
    }
  }

  const addSheet = async () => {
    try {
      const res = await createSheet(wid)   // server picks a default name
      const uiSheet = backendSheetToUI(res.sheet)
      dispatch({ type: "ADD_SHEET", sid: res.active, data: uiSheet })

      // Also update Supabase with the updated sheets list
      try {
        await supabase
          .from("workbooks")
          .update({ 
            sheets: [...sheets, res.active],
            updated_at: new Date().toISOString()
          })
          .eq("id", wid)
      } catch (error) {
        console.error("Error updating sheets in Supabase:", error)
      }
    } catch (error) {
      console.error("Error creating sheet:", error)
    }
  }

  return (
    <div className="flex items-center border-t border-gray-200 bg-white h-8">
      {sheets.map(sid => (
        <div 
          key={sid}
          onClick={() => switchTo(sid)}
          className={`px-4 py-1 text-sm cursor-pointer
            ${sid === active ? "border-t-2 border-blue-500" : "text-gray-600 hover:bg-gray-50"}`}
        >
          {sid}
        </div>
      ))}
      <button 
        onClick={addSheet}
        className="p-1 text-gray-500 hover:bg-gray-50"
      >
        <Plus size={16} />
      </button>
    </div>
  )
}
