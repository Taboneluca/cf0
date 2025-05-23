import React, { createContext, useContext, useReducer } from "react";

// Define EditingState interface
export interface EditingState {
  isEditing: boolean;
  originSheet: string | null;
  originRow: number | null;
  originCol: string | null;
  draft: string;
  caretPos: number;
}

// Define editing actions
type EditingAction =
  | { type: "START_EDIT"; sheet: string; row: number; col: string; value: string }
  | { type: "UPDATE_DRAFT"; value: string; caretPos?: number }
  | { type: "APPEND_REFERENCE"; ref: string; }
  | { type: "APPEND_RANGE_REFERENCE"; range: string; }
  | { type: "COMMIT_EDIT" }
  | { type: "CANCEL_EDIT" };

// Initial state
const initialState: EditingState = {
  isEditing: false,
  originSheet: null,
  originRow: null,
  originCol: null,
  draft: "",
  caretPos: 0,
};

// Reducer for editing state
function editingReducer(state: EditingState, action: EditingAction): EditingState {
  switch (action.type) {
    case "START_EDIT":
      return {
        isEditing: true,
        originSheet: action.sheet,
        originRow: action.row,
        originCol: action.col,
        draft: action.value,
        caretPos: action.value.length,
      };
    case "UPDATE_DRAFT":
      return {
        ...state,
        draft: action.value,
        caretPos: action.caretPos !== undefined ? action.caretPos : action.value.length,
      };
    case "APPEND_REFERENCE":
      // Insert the reference at the cursor position
      const prevDraft = state.draft;
      const newDraft = 
        prevDraft.substring(0, state.caretPos) + 
        action.ref + 
        prevDraft.substring(state.caretPos);

      return {
        ...state,
        draft: newDraft,
        caretPos: state.caretPos + action.ref.length,
      };
    case "APPEND_RANGE_REFERENCE":
      // Insert the range reference at the cursor position
      const prevRangeDraft = state.draft;
      const newRangeDraft = 
        prevRangeDraft.substring(0, state.caretPos) + 
        action.range + 
        prevRangeDraft.substring(state.caretPos);

      return {
        ...state,
        draft: newRangeDraft,
        caretPos: state.caretPos + action.range.length,
      };
    case "COMMIT_EDIT":
    case "CANCEL_EDIT":
      return initialState;
    default:
      return state;
  }
}

// Create context
type EditingContextType = {
  editingState: EditingState;
  startEdit: (sheet: string, row: number, col: string, value: string) => void;
  updateDraft: (value: string, caretPos?: number) => void;
  appendReference: (ref: string) => void;
  appendRangeReference: (range: string) => void;
  commitEdit: () => void;
  cancelEdit: () => void;
};

const EditingContext = createContext<EditingContextType | null>(null);

// Provider component
export function EditingProvider({ children }: { children: React.ReactNode }) {
  const [editingState, dispatch] = useReducer(editingReducer, initialState);

  // Helper functions for manipulating the editing state
  const startEdit = (sheet: string, row: number, col: string, value: string) => {
    dispatch({ type: "START_EDIT", sheet, row, col, value });
  };

  const updateDraft = (value: string, caretPos?: number) => {
    dispatch({ type: "UPDATE_DRAFT", value, caretPos });
  };

  const appendReference = (ref: string) => {
    dispatch({ type: "APPEND_REFERENCE", ref });
  };

  const appendRangeReference = (range: string) => {
    dispatch({ type: "APPEND_RANGE_REFERENCE", range });
  };

  const commitEdit = () => {
    dispatch({ type: "COMMIT_EDIT" });
  };

  const cancelEdit = () => {
    dispatch({ type: "CANCEL_EDIT" });
  };

  return (
    <EditingContext.Provider
      value={{ 
        editingState, 
        startEdit, 
        updateDraft, 
        appendReference, 
        appendRangeReference,
        commitEdit, 
        cancelEdit 
      }}
    >
      {children}
    </EditingContext.Provider>
  );
}

// Hook for using the editing context
export function useEditing() {
  const context = useContext(EditingContext);
  if (!context) {
    throw new Error("useEditing must be used within an EditingProvider");
  }
  return context;
}

// Helper function to create cell references
export function makeA1(row: number, col: string, sheetName: string, originSheet?: string | null): string {
  if (!row || !col) {
    console.warn("Invalid cell parameters:", { row, col });
    return "";
  }
  
  // Make sure col only contains letters and row is a positive number
  if (!/^[A-Za-z]+$/.test(col) || row <= 0) {
    console.warn("Invalid cell coordinate format:", { row, col });
    return "";
  }
  
  const cellRef = `${col}${row}`;
  
  // Add sheet prefix if referencing a different sheet
  return sheetName !== originSheet ? `${sheetName}!${cellRef}` : cellRef;
}

// Helper function to create range references
export function makeRangeA1(anchor: string, focus: string, sheetName: string, originSheet?: string | null): string {
  if (!anchor || !focus) {
    console.warn("Invalid range parameters:", { anchor, focus });
    return "";
  }

  // Extract row and column with safety checks
  // Use direct indexing instead of regex .match() to avoid potential recursion
  let anchorCol = "", anchorRow = "";
  let focusCol = "", focusRow = "";
  
  // Extract column (letters) and row (numbers) safely
  for (let i = 0; i < anchor.length; i++) {
    if (/[A-Za-z]/.test(anchor[i])) {
      anchorCol += anchor[i];
    } else if (/[0-9]/.test(anchor[i])) {
      anchorRow += anchor[i];
    }
  }
  
  for (let i = 0; i < focus.length; i++) {
    if (/[A-Za-z]/.test(focus[i])) {
      focusCol += focus[i];
    } else if (/[0-9]/.test(focus[i])) {
      focusRow += focus[i];
    }
  }
  
  // If we couldn't parse properly, return empty string
  if (!anchorCol || !anchorRow || !focusCol || !focusRow) {
    console.warn("Could not parse cell reference components:", { anchor, focus });
    return "";
  }

  const rangeRef = `${anchor}:${focus}`;
  return sheetName !== originSheet ? `${sheetName}!${rangeRef}` : rangeRef;
} 