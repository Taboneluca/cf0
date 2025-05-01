import type { SpreadsheetData } from "@/types/spreadsheet"

// Constants for default dimensions
const DEFAULT_ROWS = 100;
const DEFAULT_COLS = 30;

export function backendSheetToUI(sheet: {
  headers: string[]
  rows: number
  columns: number
  cells: any[][]
}): SpreadsheetData {
  // Ensure we have the full column set (even if backend sends fewer)
  const columns = sheet.headers.length >= DEFAULT_COLS 
    ? sheet.headers
    : [...sheet.headers, ...Array.from({length: DEFAULT_COLS - sheet.headers.length}, 
        (_, i) => String.fromCharCode(65 + sheet.headers.length + i))];
  
  // Ensure we have the full row set (even if backend sends fewer)
  const rows = sheet.rows >= DEFAULT_ROWS
    ? Array.from({ length: sheet.rows }, (_, i) => i + 1)
    : Array.from({ length: DEFAULT_ROWS }, (_, i) => i + 1);
  
  const cells: SpreadsheetData["cells"] = {};

  // Process all received cells
  for (let r = 0; r < sheet.rows; r++) {
    for (let c = 0; c < sheet.columns; c++) {
      const value = sheet.cells[r][c];
      if (value !== null && value !== undefined) {
        const id = `${sheet.headers[c]}${r + 1}`;
        cells[id] = { value: String(value) };
      }
    }
  }
  
  return { columns, rows, cells };
}

// Add this function to convert a map of backend sheets to a map of UI sheets
export function backendSheetToUIMap(sheets: Record<string, any>): Record<string, any> {
  if (!sheets) return {};
  
  const result: Record<string, any> = {};
  
  for (const [sheetName, sheet] of Object.entries(sheets)) {
    result[sheetName] = backendSheetToUI(sheet);
  }
  
  return result;
} 