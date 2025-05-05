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
  if (!sheet) {
    console.error("❌ backendSheetToUI received undefined sheet data");
    // Return a minimal valid sheet structure to prevent crashes
    return {
      columns: Array.from({length: DEFAULT_COLS}, (_, i) => String.fromCharCode(65 + i)),
      rows: Array.from({length: DEFAULT_ROWS}, (_, i) => i + 1),
      cells: {}
    };
  }

  // Log details about the sheet for debugging
  console.log("📊 Processing sheet data:", {
    hasHeaders: Array.isArray(sheet.headers),
    headerCount: Array.isArray(sheet.headers) ? sheet.headers.length : 0,
    hasRows: typeof sheet.rows === 'number',
    rowCount: sheet.rows,
    hasColumns: typeof sheet.columns === 'number',
    columnCount: sheet.columns,
    hasCells: Array.isArray(sheet.cells),
    cellRowCount: Array.isArray(sheet.cells) ? sheet.cells.length : 0
  });

  // Ensure headers are an array and have the expected length
  const safeHeaders = Array.isArray(sheet.headers) ? sheet.headers : [];
  
  // Ensure we have the full column set (even if backend sends fewer)
  const columns = safeHeaders.length >= DEFAULT_COLS 
    ? safeHeaders
    : [...safeHeaders, ...Array.from({length: DEFAULT_COLS - safeHeaders.length}, 
        (_, i) => String.fromCharCode(65 + safeHeaders.length + i))];
  
  // Ensure we have the full row set (even if backend sends fewer)
  const rowCount = typeof sheet.rows === 'number' && sheet.rows > 0 ? sheet.rows : DEFAULT_ROWS;
  const rows = rowCount >= DEFAULT_ROWS
    ? Array.from({ length: rowCount }, (_, i) => i + 1)
    : Array.from({ length: DEFAULT_ROWS }, (_, i) => i + 1);
  
  const cells: SpreadsheetData["cells"] = {};

  // Ensure sheet.cells is an array before processing
  const safeCells = Array.isArray(sheet.cells) ? sheet.cells : [];

  // Process all received cells with safety checks
  for (let r = 0; r < rowCount; r++) {
    // Skip if this row doesn't exist in the data
    if (!Array.isArray(safeCells[r])) continue;
    
    for (let c = 0; c < (sheet.columns || DEFAULT_COLS); c++) {
      // Skip if column header doesn't exist or column index is out of bounds
      if (!columns[c] || c >= safeCells[r].length) continue;
      
      const value = safeCells[r][c];
      if (value !== null && value !== undefined) {
        const id = `${columns[c]}${r + 1}`;
        cells[id] = { value: String(value) };
      }
    }
  }
  
  return { columns, rows, cells };
}

// Add this function to convert a map of backend sheets to a map of UI sheets
export function backendSheetToUIMap(sheets: Record<string, any>): Record<string, any> {
  if (!sheets) {
    console.warn("⚠️ backendSheetToUIMap received undefined sheets data");
    return {};
  }
  
  const result: Record<string, any> = {};
  
  try {
    for (const [sheetName, sheet] of Object.entries(sheets)) {
      try {
        result[sheetName] = backendSheetToUI(sheet);
      } catch (error) {
        console.error(`❌ Error transforming sheet ${sheetName}:`, error);
        // Skip this sheet but continue with others
      }
    }
  } catch (error) {
    console.error("❌ Error in backendSheetToUIMap:", error);
  }
  
  return result;
} 