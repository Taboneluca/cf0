// Cell reference pattern (e.g., A1, B2, etc.) - case insensitive
const CELL_REF_PATTERN = /([A-Za-z]+)(\d+)/gi

// Cross-sheet reference pattern (e.g., Sheet1!A1) - case insensitive
const XREF_PATTERN = /([A-Za-z_][A-Za-z0-9_]*)!([A-Za-z]+)(\d+)/gi

// Basic operators
const OPERATORS = {
  "+": (a: number, b: number) => a + b,
  "-": (a: number, b: number) => a - b,
  "*": (a: number, b: number) => a * b,
  "/": (a: number, b: number) => a / b,
  "^": (a: number, b: number) => Math.pow(a, b),
}

// Basic functions
const FUNCTIONS: { [key: string]: (...args: number[]) => number } = {
  SUM: (...args) => args.reduce((sum, val) => sum + val, 0),
  AVG: (...args) => (args.length ? args.reduce((sum, val) => sum + val, 0) / args.length : 0),
  MIN: (...args) => Math.min(...args),
  MAX: (...args) => Math.max(...args),
  COUNT: (...args) => args.length,
  ABS: (a) => Math.abs(a),
  ROUND: (a, decimals = 0) => Number(Math.round(Number(a + "e" + decimals)) + "e-" + decimals),
}

// Check if a string is a formula (starts with =)
export const isFormula = (value: string): boolean => {
  return value.trim().startsWith("=") && value.trim().length > 1
}

// Interface for cell references, including cross-sheet references
export interface CellReference {
  sheet?: string; // Optional sheet name for cross-sheet references
  cell: string;   // Cell reference (e.g., 'A1')
}

// Get cell references from a formula
export const getCellReferences = (formula: string): CellReference[] => {
  const refs: CellReference[] = []
  let match: RegExpExecArray | null

  // First find cross-sheet references
  XREF_PATTERN.lastIndex = 0
  while ((match = XREF_PATTERN.exec(formula)) !== null) {
    const sheet = match[1]
    const cell = `${match[2].toUpperCase()}${match[3]}`
    refs.push({ sheet, cell })
  }

  // Then find plain cell references
  CELL_REF_PATTERN.lastIndex = 0
  while ((match = CELL_REF_PATTERN.exec(formula)) !== null) {
    // Skip if already found as part of a cross-sheet reference
    const cellRef = `${match[1].toUpperCase()}${match[2]}`
    
    // Check if this is part of a cross-sheet reference we already found
    const isPartOfXref = refs.some(ref => 
      ref.sheet && formula.includes(`${ref.sheet}!${cellRef}`)
    )
    
    if (!isPartOfXref) {
      refs.push({ cell: cellRef })
    }
  }

  return refs
}

// Create a safe sandbox for formula evaluation
const createFormulaSandbox = () => {
  return {
    SUM: (...args: number[]) => args.reduce((sum, val) => sum + val, 0),
    AVG: (...args: number[]) => (args.length ? args.reduce((sum, val) => sum + val, 0) / args.length : 0),
    MIN: Math.min,
    MAX: Math.max,
    COUNT: (...args: any[]) => args.length,
    ABS: Math.abs,
    ROUND: (a: number, decimals = 0) => Number(Math.round(Number(a + "e" + decimals)) + "e-" + decimals),
    
    // Helper for getting cell values
    get: (sheet: string, cell: string, getCellValue: Function, activeSheet: string) => {
      const value = getCellValue(cell, sheet === "currentSheet" ? activeSheet : sheet);
      return isNaN(Number(value)) ? 0 : Number(value);
    },
    
    // Helper for ranges (simplified implementation)
    range: (start: string, end: string) => {
      // This is a placeholder - in a real implementation, you'd extract all cells in the range
      return [0]; // Return dummy value for now
    }
  };
};

// Evaluate a formula
export const evaluateFormula = (
  formula: string, 
  getCellValue: (cellRef: string, sheet?: string) => string,
  activeSheet?: string, 
  workbookData?: Record<string, any>
): string => {
  if (!isFormula(formula)) {
    return formula
  }

  try {
    // Circular reference detection
    const visitedCells = new Set<string>()
    const evaluated = new Map<string, string>()
    
    // Remove the = sign
    let expression = formula.substring(1).trim()

    // Helper function to handle possible circular references
    const evaluateReference = (ref: CellReference): string => {
      const fullRef = ref.sheet ? `${ref.sheet}!${ref.cell}` : ref.cell
      
      // Check for circular references
      if (visitedCells.has(fullRef)) {
        return "#CIRC!"
      }
      
      // Add to visited set
      visitedCells.add(fullRef)
      
      // Try to get the cell value (from the right sheet if specified)
      try {
        const value = getCellValue(ref.cell, ref.sheet)
        
        // Handle nested formulas
        if (isFormula(value)) {
          // Prevent infinite recursion
          if (evaluated.has(fullRef)) {
            return evaluated.get(fullRef) || "#CIRC!"
          }
          
          // Evaluate the nested formula
          const result = evaluateFormula(value, getCellValue, ref.sheet || activeSheet, workbookData)
          evaluated.set(fullRef, result)
          return result
        }
        
        return value === "" ? "0" : value
      } catch (error) {
        console.error(`Error evaluating reference ${fullRef}:`, error)
        return "#REF!"
      } finally {
        // Remove from visited set when done
        visitedCells.delete(fullRef)
      }
    }

    // Replace cell references with their values
    const cellRefs = getCellReferences(expression)

    // Replace cell references with unique tokens first
    const replacements: Record<string, string> = {};

    cellRefs.forEach((ref, i) => {
      const token = `__REF_${i}__`;
      const getCall = ref.sheet
        ? `get("${ref.sheet}","${ref.cell}",getCellValue,"${activeSheet || ''}")`
        : `get("currentSheet","${ref.cell}",getCellValue,"${activeSheet || ''}")`;

      const pattern = ref.sheet
        ? new RegExp(`${ref.sheet}\\!${ref.cell}`, 'gi')
        : new RegExp(`\\b${ref.cell}\\b`, 'gi');

      expression = expression.replace(pattern, token);
      replacements[token] = getCall;
    });

    // Once all tokens are in place, expand them
    Object.keys(replacements).forEach(token => {
      expression = expression.replaceAll(token, replacements[token]);
    });

    // Handle built-in functions by replacing with sandbox functions
    for (const funcName of Object.keys(FUNCTIONS)) {
      const funcRegex = new RegExp(`${funcName}\\(([^)]+)\\)`, "gi")
      expression = expression.replace(funcRegex, (match, args) => {
        // Don't actually evaluate here, keep the function call intact
        return match;
      })
    }

    // Defensive check for empty expression
    if (!expression.trim()) return "#EMPTY!"
    
    // Check for incomplete expressions that would cause syntax errors
    if (/[\+\-\*\/\^]$/.test(expression.trim())) return "#ERROR!"

    // Create sandbox with helper functions and built-in functions
    const sandbox = createFormulaSandbox();
    
    // Add getCellValue to the sandbox
    const sandboxWithContext = {
      ...sandbox,
      getCellValue: getCellValue
    };
    
    // Extract function names for the Function constructor
    const functionNames = [...Object.keys(sandboxWithContext)];
    
    // Evaluate the expression safely within the sandbox
    try {
      try {
        const evaluator = Function(...functionNames, `"use strict"; return (${expression})`);
        const result = evaluator(...functionNames.map(name => sandboxWithContext[name as keyof typeof sandboxWithContext]));

        // Format the result
        if (typeof result === "number") {
          // Handle special cases
          if (isNaN(result)) return "#NaN"
          if (!isFinite(result)) return "#DIV/0!"

          // Format number to avoid excessive decimal places
          return result.toString()
        }

        return result?.toString() || "#ERROR!";
      } catch (error) {
        console.error("Expression evaluation error:", error);
        console.error("Failed expression:", expression);
        return "#ERROR!";
      }
    } catch (error) {
      console.error("Formula evaluation error:", error)
      return "#ERROR!"
    }
  } catch (error) {
    console.error("Formula evaluation error:", error)
    return "#ERROR!"
  }
}

// Detect circular references
export const detectCircularReferences = (
  startCellId: string,
  formula: string,
  getCellValue: (cellId: string, sheet?: string) => string,
  visited: Set<string> = new Set(),
  activeSheet?: string,
): boolean => {
  if (visited.has(startCellId)) {
    return true // Circular reference detected
  }

  visited.add(startCellId)

  const cellRefs = getCellReferences(formula)

  for (const ref of cellRefs) {
    const fullRef = ref.sheet ? `${ref.sheet}!${ref.cell}` : ref.cell
    
    try {
      const cellValue = getCellValue(ref.cell, ref.sheet)

      if (isFormula(cellValue)) {
        // Create a copy of visited set for this branch
        const branchVisited = new Set(visited)
        
        if (detectCircularReferences(fullRef, cellValue, getCellValue, branchVisited, ref.sheet || activeSheet)) {
          return true
        }
      }
    } catch (error) {
      console.error(`Error checking references for ${fullRef}:`, error)
    }
  }

  return false
}
