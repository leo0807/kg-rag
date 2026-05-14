"use client";

import { Upload } from "lucide-react";

interface Props {
  selectedFileName: string | null;
  docId: string;
  onDocIdChange: (value: string) => void;
  onFileChange: (file: File | null) => void;
}

export function ObjectiveEvalFilePicker({
  selectedFileName,
  docId,
  onDocIdChange,
  onFileChange,
}: Props) {
  return (
    <div className="space-y-3">
      <label className="block">
        <div className="text-xs text-gray-500 mb-2">源文档（自动检测优先）</div>
        <select
          value={docId}
          onChange={(e) => onDocIdChange(e.target.value)}
          className="block w-full rounded-lg border border-gray-800 bg-gray-950/70 px-3 py-2 text-sm text-gray-200 placeholder:text-gray-600 focus:border-indigo-500 focus:outline-none"
        >
          <option value="">自动检测（推荐）</option>
          <option value="CPS1000">CPS1000 通用密封</option>
          <option value="CPS7251">CPS7251 密封圈安装</option>
        </select>
      </label>
      <label className="block">
        <div className="text-xs text-gray-500 mb-2">客观题文档</div>
        <input
          type="file"
          accept=".doc,.docx,.wps"
          onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-gray-300 file:mr-4 file:px-3 file:py-2 file:rounded-lg file:border-0 file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
        />
      </label>
      <div className="flex items-center gap-2 rounded-xl border border-gray-800 bg-gray-950/70 px-3 py-2 text-xs text-gray-400">
        <Upload size={14} className="text-gray-500" />
        <span className="truncate">
          {selectedFileName ? `已选择：${selectedFileName}` : "尚未选择文件"}
        </span>
      </div>
    </div>
  );
}
