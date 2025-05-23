import React from 'react';
import { Button } from './ui/button';
import { X, Check } from 'lucide-react';

interface PendingBarProps {
  visible: boolean;
  pendingCount: number;
  onApply: () => void;
  onReject: () => void;
}

export function PendingBar({ visible, pendingCount, onApply, onReject }: PendingBarProps) {
  if (!visible) return null;
  
  return (
    <div className="flex items-center justify-between p-2 bg-amber-50 border-t border-amber-200 text-amber-800">
      <div className="text-sm">
        <span className="font-medium">{pendingCount} pending {pendingCount === 1 ? 'change' : 'changes'}</span>
        <span className="ml-2 text-amber-600 text-xs">Review and apply changes to your sheet</span>
      </div>
      <div className="flex gap-2">
        <Button 
          onClick={onApply}
          size="sm"
          className="bg-green-600 hover:bg-green-700 text-white"
        >
          <Check className="mr-1 h-4 w-4" />
          Apply
        </Button>
        <Button 
          onClick={onReject}
          size="sm"
          variant="outline"
          className="border-amber-300 hover:bg-amber-100 text-amber-800"
        >
          <X className="mr-1 h-4 w-4" />
          Reject
        </Button>
      </div>
    </div>
  );
} 