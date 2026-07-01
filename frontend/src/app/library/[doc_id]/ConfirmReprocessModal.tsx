"use client";

import { Clock } from "lucide-react";

interface Props {
  selectedLabels: string[];
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmReprocessModal({ selectedLabels, onCancel, onConfirm }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onCancel}>
      <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 w-80 shadow-2xl"
        onClick={e => e.stopPropagation()}>
        <h2 className="text-sm font-semibold text-white mb-2">确认重新处理？</h2>
        <p className="text-xs text-gray-400 mb-3">将运行以下管道：</p>
        <ul className="text-xs text-indigo-300 mb-3 list-disc list-inside space-y-0.5">
          {selectedLabels.map(label => <li key={label}>{label}</li>)}
        </ul>
        <p className="text-xs text-gray-500 mb-4 flex items-center gap-1">
          <Clock size={11} />处理前将自动拍摄快照，可随时回滚
        </p>
        <div className="flex gap-2">
          <button onClick={onCancel}
            className="flex-1 py-1.5 rounded-lg border border-gray-700 text-xs text-gray-400 hover:text-white transition-colors">
            取消
          </button>
          <button onClick={onConfirm}
            className="flex-1 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 transition-colors">
            确认
          </button>
        </div>
      </div>
    </div>
  );
}
