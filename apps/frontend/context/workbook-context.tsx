"use client"

import React, {createContext, useContext, useReducer, useEffect, useState} from "react"
import { usePathname } from 'next/navigation'
import type { WorkbookState, SpreadsheetData } from "@/types/spreadsheet"
import { fetchSheet } from "@/utils/backend"
import { supabase } from "@/lib/supabase/client"

// Add formula editing interface
interface FormulaEdit {
  active: boolean
  originSheet: string        // where the edit began
  cellId: string             // e.g. "B4"
  buffer: string             // current text, starts with "="
  anchor: number             // insert-point inside buffer
}

// Add range selection interface
interface RangeSelection {
  sheet: string
  anchor: string            // where mouse-down started
  focus: string             // where mouse-up ended
}

type Action =
  | {type:"INIT"; wid:string; sheets:string[]; active:string; data: Record<string,SpreadsheetData>}
  | {type:"SWITCH"; sid:string}
  | {type:"UPDATE_SHEET"; sid:string; data:SpreadsheetData}
  | {type:"ADD_SHEET"; sid:string; data:SpreadsheetData}
  | {type:"MERGE_SHEETS_DATA"; data: Record<string,SpreadsheetData>}
  | {type:"START_FORMULA_EDIT"; data: FormulaEdit}
  | {type:"UPDATE_FORMULA_BUFFER"; buffer:string}
  | {type:"END_FORMULA_EDIT"; commit:boolean}
  | {type:"SELECT_CELL"; cell:string}
  | {type:"START_RANGE"; sheet:string; anchor:string}
  | {type:"UPDATE_RANGE"; focus:string}
  | {type:"CLEAR_RANGE"}

function reducer(state:WorkbookState, action:Action):WorkbookState {
  switch(action.type){
    case "INIT": return {wid:action.wid, sheets:action.sheets,
                         active:action.active, data:action.data,
                         formula: {active: false}}
    case "SWITCH": return {...state, active:action.sid}
    case "UPDATE_SHEET": return {...state, data:{...state.data,[action.sid]:{...action.data}}}
    case "ADD_SHEET": return {...state,
                              sheets:[...state.sheets,action.sid],
                              active:action.sid,
                              data:{...state.data,[action.sid]:{...action.data}}}
    case "MERGE_SHEETS_DATA": return {...state, data:{...state.data, ...action.data}}
    case "START_FORMULA_EDIT": return {...state, formula: action.data}
    case "UPDATE_FORMULA_BUFFER": 
      return {
        ...state, 
        formula: {
          ...state.formula, 
          buffer: action.buffer,
          anchor: action.buffer.length // Keep caret at end for better typing experience
        }
      }
    case "END_FORMULA_EDIT": return {...state, formula: {active: false}}
    case "SELECT_CELL": return {...state, selected: action.cell, range: undefined}
    case "START_RANGE": return {
      ...state, 
      range: {
        sheet: action.sheet,
        anchor: action.anchor,
        focus: action.anchor
      }
    }
    case "UPDATE_RANGE": return {
      ...state, 
      range: state.range ? {
        ...state.range,
        focus: action.focus
      } : undefined
    }
    case "CLEAR_RANGE": return {...state, range: undefined}
  }
}

const Ctx = createContext<[WorkbookState, React.Dispatch<Action>, boolean] | null>(null)
export const useWorkbook = ()=> {
  const v = useContext(Ctx)
  if (!v) throw new Error("Workbook context missing")
  return v
}

export function WorkbookProvider({children}:{children:React.ReactNode}){
  const pathname = usePathname();
  const [loading, setLoading] = useState(true);
  
  // Extract workbook ID from URL or use default
  const getWorkbookId = () => {
    // Match the workbook ID pattern /workbook/some-id-here
    const match = pathname?.match(/\/workbook\/([^\/]+)/);
    if (match && match[1]) {
      return match[1];
    }
    
    // If not in URL, return default
    return "default";
  };
  
  const [state, dispatch] = useReducer(reducer, {
    wid: getWorkbookId(), 
    sheets: [], 
    active: "Sheet1", 
    data: {},
    formula: { active: false }
  } as WorkbookState);
  
  // Load initial sheet data
  useEffect(() => {
    const wid = getWorkbookId();
    if (!wid) return;
    
    setLoading(true);
    
    (async () => {
      try {
        // First get the list of sheets from Supabase
        const { data: workbookData } = await supabase
          .from("workbooks")
          .select("sheets")
          .eq("id", wid)
          .single();
        
        // Default to Sheet1 if no sheets found
        const sheetNames = workbookData?.sheets || ["Sheet1"];
        
        // Fetch the active sheet data (first sheet)
        const firstSheet = sheetNames[0] || "Sheet1";
        const uiSheet = await fetchSheet(wid, firstSheet);
        
        // Initialize with the first sheet loaded
        dispatch({
          type: "INIT", 
          wid, 
          sheets: sheetNames, 
          active: firstSheet,
          data: { [firstSheet]: uiSheet }
        });
      } catch (error) {
        console.error("Error fetching initial workbook data:", error);
        
        // Fallback to default init with Sheet1
        try {
          const uiSheet = await fetchSheet(wid, "Sheet1");
          dispatch({
            type: "INIT", 
            wid, 
            sheets: ["Sheet1"], 
            active: "Sheet1",
            data: { "Sheet1": uiSheet }
          });
        } catch (fallbackError) {
          console.error("Error fetching fallback sheet:", fallbackError);
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [pathname]);
  
  return <Ctx.Provider value={[state, dispatch, loading]}>{children}</Ctx.Provider>
} 