"use client"

import { useRouter } from "next/navigation"

export default function ToolbarRibbon() {
  const router = useRouter();

  const createNewWorkbook = () => {
    const newId = crypto.randomUUID();
    router.push(`/workbook/${newId}`);
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
            <button className="p-1 rounded hover:bg-gray-100 transition-colors">
              <span className="text-xs text-gray-700">B</span>
            </button>
            <button className="p-1 rounded hover:bg-gray-100 transition-colors">
              <span className="text-xs text-gray-700 italic">I</span>
            </button>
            <button className="p-1 rounded hover:bg-gray-100 transition-colors">
              <span className="text-xs text-gray-700 underline">U</span>
            </button>
          </div>
          <div className="h-4 w-px bg-gray-200"></div>
          <div className="flex items-center space-x-2">
            <button className="p-1 rounded hover:bg-gray-100 transition-colors">
              <span className="text-xs text-gray-700">Format</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
