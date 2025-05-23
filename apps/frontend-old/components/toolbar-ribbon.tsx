"use client"

import { useRouter } from "next/navigation"
import { Bold, Italic, Underline, AlignLeft, AlignCenter, AlignRight } from "lucide-react"
import { useWorkbook } from "@/context/workbook-context"
import { CellStyle } from "@/types/spreadsheet"
import { useState } from "react"

export default function ToolbarRibbon() {
  const router = useRouter();
  const [wb, dispatch] = useWorkbook();
  const { selected, range, active, data } = wb;

  const createNewWorkbook = () => {
    const newId = crypto.randomUUID();
    router.push(`/workbook/${newId}`);
  };

  // Function to format selected cells or range
  const formatCells = (styleProperty: keyof CellStyle, value: any) => {
    // If nothing is selected, return
    if (!selected && !range) return;

    // Helper to get the cell IDs to format
    const getCellsToFormat = (): string[] => {
      // If a single cell is selected
      if (selected) return [selected];
      
      // If a range is selected
      if (range && range.sheet === active) {
        const cellsToFormat: string[] = [];
        const sheet = data[active];
        
        // Calculate range boundaries
        const { anchor, focus } = range;
        const anchorMatch = anchor.match(/^([A-Za-z]+)(\d+)$/);
        const focusMatch = focus.match(/^([A-Za-z]+)(\d+)$/);
        
        if (!anchorMatch || !focusMatch || !sheet) return [];
        
        const anchorCol = anchorMatch[1];
        const anchorRow = parseInt(anchorMatch[2]);
        const focusCol = focusMatch[1];
        const focusRow = parseInt(focusMatch[2]);
        
        // Get column indices
        const anchorColIndex = sheet.columns.indexOf(anchorCol);
        const focusColIndex = sheet.columns.indexOf(focusCol);
        
        if (anchorColIndex === -1 || focusColIndex === -1) return [];
        
        // Calculate min/max bounds
        const minRow = Math.min(anchorRow, focusRow);
        const maxRow = Math.max(anchorRow, focusRow);
        const minColIndex = Math.min(anchorColIndex, focusColIndex);
        const maxColIndex = Math.max(anchorColIndex, focusColIndex);
        
        // Collect all cell IDs within the range
        for (let r = minRow; r <= maxRow; r++) {
          for (let c = minColIndex; c <= maxColIndex; c++) {
            const col = sheet.columns[c];
            cellsToFormat.push(`${col}${r}`);
          }
        }
        
        return cellsToFormat;
      }
      
      return [];
    };

    // Get all cells that need to be formatted
    const cellsToFormat = getCellsToFormat();
    
    // Update each cell's style in the current sheet
    const updatedCells = { ...data[active].cells };
    
    cellsToFormat.forEach(cellId => {
      const cell = updatedCells[cellId] || { value: '' };
      const currentStyle = cell.style || {};
      
      // Toggle the value if it's a boolean property, otherwise set it
      const newValue = typeof value === 'boolean' && currentStyle[styleProperty] === value 
        ? !value 
        : value;
      
      updatedCells[cellId] = {
        ...cell,
        style: {
          ...currentStyle,
          [styleProperty]: newValue
        }
      };
    });
    
    // Update the sheet with the new styles
    dispatch({
      type: "UPDATE_SHEET",
      sid: active,
      data: {
        ...data[active],
        cells: updatedCells
      }
    });
  };

  return (
    <div className="border-b border-gray-200 bg-white">
      <div className="flex p-1">
        <div className="flex items-center space-x-4 px-2">
          <div className="font-medium text-sm text-gray-700">File</div>
          <div className="font-medium text-sm text-gray-700">Home</div>
          <div className="font-medium text-sm text-gray-700">Insert</div>
          <div className="font-medium text-sm text-gray-700">Data</div>
          <div className="font-medium text-sm text-gray-700">View</div>
          <button 
            onClick={createNewWorkbook}
            className="ml-4 px-2 py-1 text-xs text-white bg-blue-500 rounded hover:bg-blue-600 transition-colors"
          >
            New Workbook
          </button>
        </div>
      </div>
      <div className="flex items-center border-t border-gray-100 p-1">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <button 
              className="p-1 rounded hover:bg-gray-100 transition-colors"
              onClick={() => formatCells('bold', true)}
              title="Bold"
            >
              <Bold size={16} className="text-gray-700" />
            </button>
            <button 
              className="p-1 rounded hover:bg-gray-100 transition-colors"
              onClick={() => formatCells('italic', true)}
              title="Italic"
            >
              <Italic size={16} className="text-gray-700" />
            </button>
            <button 
              className="p-1 rounded hover:bg-gray-100 transition-colors"
              onClick={() => formatCells('underline', true)}
              title="Underline"
            >
              <Underline size={16} className="text-gray-700" />
            </button>
          </div>
          <div className="h-4 w-px bg-gray-200"></div>
          <div className="flex items-center space-x-2">
            <button 
              className="p-1 rounded hover:bg-gray-100 transition-colors"
              onClick={() => formatCells('textAlign', 'left')}
              title="Align Left"
            >
              <AlignLeft size={16} className="text-gray-700" />
            </button>
            <button 
              className="p-1 rounded hover:bg-gray-100 transition-colors"
              onClick={() => formatCells('textAlign', 'center')}
              title="Align Center"
            >
              <AlignCenter size={16} className="text-gray-700" />
            </button>
            <button 
              className="p-1 rounded hover:bg-gray-100 transition-colors"
              onClick={() => formatCells('textAlign', 'right')}
              title="Align Right"
            >
              <AlignRight size={16} className="text-gray-700" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
