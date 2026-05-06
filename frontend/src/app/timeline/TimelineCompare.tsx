"use client";

import { useState } from "react";
import { fetchApi } from "@/lib/api";
import { GitCompare } from "lucide-react";

interface CompareDoc {
  doc_id: string; title: string; added_on: string; version: string; section_count: number;
}
interface CompareResult {
  from_date: string; to_date: string;
  new_docs: CompareDoc[]; docs_count: number; sections_count: number;
}

export function TimelineCompare({ onClose }: { onClose: () => void }) {
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleCompare() {
    if (!fromDate || !toDate) return;
    setLoading(true); setErr(null);
    try {
      const r = await fetchApi<CompareResult>(`/api/timeline/compare?from_date=${fromDate}&to_date=${toDate}`);
      setResult(r);
    } catch { setErr("对比失败"); }
    finally { setLoading(false); }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 text-sm font-medium">
          <GitCompare size={14} className="text-indigo-400" /> 版本对比
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-white text-xs">✕</button>
      </div>

      <div className="p-4 space-y-3 shrink-0">
        {[["起始日期", fromDate, setFromDate], ["截止日期", toDate, setToDate]].map(([label, val, setter]) => (
          <div key={label as string}>
            <label className="text-xs text-gray-400 block mb-1">{label as string}</label>
            <input type="date" value={val as string} onChange={e => (setter as (v: string) => void)(e.target.value)}
              className="w-full rounded-lg bg-gray-800 border border-gray-700 px-2 py-1.5 text-xs text-white focus:border-indigo-500 outline-none" />
          </div>
        ))}
        {err && <p className="text-xs text-red-400">{err}</p>}
        <button onClick={handleCompare} disabled={!fromDate || !toDate || loading}
          className="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium disabled:opacity-50 transition-colors">
          {loading ? "对比中…" : "开始对比"}
        </button>
      </div>

      {result && (
        <div className="flex-1 overflow-y-auto border-t border-gray-800">
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-2 gap-2">
              {[["新增文档", result.docs_count, "emerald"], ["新增章节", result.sections_count, "blue"]].map(([label, val, color]) => (
                <div key={label as string} className={`rounded-lg bg-${color}-950/40 border border-${color}-800/40 px-3 py-2 text-center`}>
                  <div className={`text-${color}-400 font-bold text-lg`}>{val as number}</div>
                  <div className="text-[10px] text-gray-400">{label as string}</div>
                </div>
              ))}
            </div>
            <div className="text-xs text-gray-400 font-medium">新增文档（{result.from_date} → {result.to_date}）</div>
            <div className="space-y-1.5">
              {result.new_docs.length === 0
                ? <p className="text-xs text-gray-500">该时间段内无新增文档</p>
                : result.new_docs.map(doc => (
                    <div key={doc.doc_id} className="rounded-lg border border-gray-800 bg-gray-900 px-3 py-2">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs text-indigo-300">{doc.doc_id}</span>
                        <span className="text-[10px] text-gray-500">{doc.added_on}</span>
                      </div>
                      <div className="text-xs text-gray-300 mt-0.5 truncate">{doc.title}</div>
                      <div className="text-[10px] text-gray-500 mt-0.5">
                        {doc.section_count} 章节{doc.version ? ` · v${doc.version}` : ""}
                      </div>
                    </div>
                  ))
              }
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
