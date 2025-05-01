export interface CellData {
  value: string
  // You can add more properties like formatting, formulas, etc.
}

export interface SpreadsheetData {
  columns: string[]
  rows: number[]
  cells: {
    [cellId: string]: CellData
  }
}

export interface FormulaEdit {
  active: boolean
  originSheet?: string    // where the edit began
  cellId?: string         // e.g. "B4"
  buffer?: string         // current text, starts with "="
  anchor?: number         // insert-point inside buffer
}

export interface WorkbookState {
  wid: string
  sheets: string[]
  active: string          // sheet id
  data: Record<string, SpreadsheetData>   // sid → sheet
  formula: FormulaEdit
  selected?: string       // currently selected cell
}

export interface Message {
  role: "user" | "assistant" | "system"
  content: string
}
