export interface CellData {
  value: string
  style?: CellStyle
  // You can add more properties like formatting, formulas, etc.
}

export interface CellStyle {
  bold?: boolean
  italic?: boolean
  underline?: boolean
  color?: string
  backgroundColor?: string
  textAlign?: 'left' | 'center' | 'right'
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

export interface RangeSelection {
  sheet: string
  anchor: string         // where mouse-down started
  focus: string          // where mouse-up ended
}

export interface WorkbookState {
  wid: string
  sheets: string[]
  active: string          // sheet id
  data: Record<string, SpreadsheetData>   // sid → sheet
  formula: FormulaEdit
  selected?: string       // currently selected cell
  range?: RangeSelection  // currently selected range of cells
}

export interface Message {
  role: "user" | "assistant" | "system"
  content: string
  id?: string
  status?: 'thinking' | 'streaming' | 'complete'
  lastAddedSection?: string  // Tracks the most recently added section header
}
