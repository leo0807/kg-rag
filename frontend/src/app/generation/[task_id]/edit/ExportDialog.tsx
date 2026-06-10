"use client";

import { useState } from "react";
import { getApiBaseUrl } from "@/lib/api";

interface Props {
  taskId:   string;
  taskName: string;
  onClose:  () => void;
}

export function ExportDialog({ taskId, taskName, onClose }: Props) {
  const [fmt, setFmt]       = useState<"docx" | "markdown">("docx");
  const [loading, setLoading] = useState(false);

  const doExport = async () => {
    setLoading(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const url = `${getApiBaseUrl()}/api/generation/tasks/${taskId}/export?fmt=${fmt}`;
      const res = await fetch(url, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("导出失败");
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${taskName}.${fmt === "docx" ? "docx" : "md"}`;
      a.click();
      URL.revokeObjectURL(a.href);
      onClose();
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-80 space-y-4">
        <h2 className="text-sm font-semibold text-gray-100">导出规范草稿</h2>

        <div className="space-y-2">
          {(["docx", "markdown"] as const).map(f => (
            <label key={f}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                fmt === f
                  ? "border-indigo-600 bg-indigo-900/20"
                  : "border-gray-800 hover:border-gray-700"
              }`}>
              <input type="radio" name="fmt" value={f} checked={fmt === f}
                onChange={() => setFmt(f)} className="hidden" />
              <div className={`w-3 h-3 rounded-full border-2 ${
                fmt === f ? "border-indigo-500 bg-indigo-500" : "border-gray-600"
              }`} />
              <div>
                <div className="text-xs text-gray-200">{f === "docx" ? "Word 文档 (.docx)" : "Markdown (.md)"}</div>
                <div className="text-[10px] text-gray-600">
                  {f === "docx" ? "符合 COMAC 排版模板" : "纯文本，便于版本对比"}
                </div>
              </div>
            </label>
          ))}
        </div>

        <div className="flex gap-2 justify-end">
          <button onClick={onClose}
            className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-300">取消</button>
          <button onClick={doExport} disabled={loading}
            className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs rounded-lg">
            {loading ? "导出中…" : "导出"}
          </button>
        </div>
      </div>
    </div>
  );
}
