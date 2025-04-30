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

export interface WorkbookState {
  wid: string
  sheets: string[]
  active: string          // sheet id
  data: Record<string, SpreadsheetData>   // sid → sheet
}

export interface Message {
  role: "user" | "assistant" | "system"
  content: string
}
