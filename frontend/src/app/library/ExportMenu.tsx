"use client";

import { useState, useRef, useEffect } from "react";
import { Download, Loader2, ChevronDown } from "lucide-react";

interface ExportOption {
  label: string;
  url: string;
  body: object;
  filename: string;
}

const OPTIONS: ExportOption[] = [
  { label: "导出章节（JSON）",          url: "/api/export/sections", body: { format: "json" },     filename: "cps_sections.json" },
  { label: "导出章节（Markdown）",      url: "/api/export/sections", body: { format: "markdown" }, filename: "cps_sections.md" },
  { label: "导出章节（Excel）",         url: "/api/export/sections", body: { format: "excel" },    filename: "cps_export.xlsx" },
  { label: "导出图谱结构（GraphML）",   url: "/api/export/graph",    body: { format: "graphml" },  filename: "cps_graph.graphml" },
  { label: "导出问答训练数据（JSONL）", url: "/api/export/qa-pairs", body: { limit: 1000 },         filename: "cps_qa_pairs.jsonl" },
];

export function ExportMenu({ selectedDocIds = [] }: { selectedDocIds?: string[] }) {
  const [open, setOpen] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [maskPii, setMaskPii] = useState(true);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);

  async function handleExport(opt: ExportOption) {
    setOpen(false);
    setExporting(opt.label);
    setToast(`正在导出：${opt.label}…`);
    try {
      const token = localStorage.getItem("token") ?? "";
      const body = selectedDocIds.length > 0
        ? { ...opt.body, doc_ids: selectedDocIds, mask_pii: maskPii }
        : { ...opt.body, mask_pii: maskPii };
      const resp = await fetch(opt.url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = opt.filename;
      a.click();
      URL.revokeObjectURL(a.href);
      setToast(`✓ ${opt.label} 下载完成`);
    } catch (e) {
      setToast(`✕ 导出失败：${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setExporting(null);
      setTimeout(() => setToast(null), 3000);
    }
  }

  return (
    <>
      <div ref={ref} className="relative">
        <button
          onClick={() => setOpen(v => !v)}
          disabled={!!exporting}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 border border-gray-700 hover:border-gray-500 text-gray-300 hover:text-white text-sm rounded-lg transition-colors disabled:opacity-50"
        >
          {exporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
          导出数据
          <ChevronDown size={11} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        {open && (
          <div className="absolute right-0 top-full mt-1 w-56 rounded-xl border border-gray-700 bg-gray-900 shadow-2xl z-50 overflow-hidden">
            {/* 脱敏开关 */}
            <label className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-800 cursor-pointer hover:bg-gray-800 transition-colors">
              <input
                type="checkbox"
                checked={maskPii}
                onChange={(e) => setMaskPii(e.target.checked)}
                className="accent-indigo-500"
              />
              <span className="text-xs text-gray-400">
                导出时脱敏个人信息
                <span className="block text-[10px] text-gray-600">编制人、手机号、邮箱等</span>
              </span>
            </label>
            {OPTIONS.map(opt => (
              <button key={opt.label} onClick={() => handleExport(opt)}
                className="w-full text-left px-4 py-2.5 text-xs text-gray-300 hover:bg-gray-800 hover:text-white transition-colors">
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {toast && (
        <div className="fixed bottom-6 right-6 z-50 max-w-sm px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-xs text-gray-200 shadow-2xl">
          {toast}
        </div>
      )}
    </>
  );
}
