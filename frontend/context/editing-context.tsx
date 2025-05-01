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

// Helper function to create A1 references
export function makeA1(row: number, col: string, sheetName: string, originSheet?: string | null): string {
  const cellRef = `${col}${row}`;
  // Only add sheet prefix if we're referencing a different sheet than the origin
  return sheetName !== originSheet ? `${sheetName}!${cellRef}` : cellRef;
} 