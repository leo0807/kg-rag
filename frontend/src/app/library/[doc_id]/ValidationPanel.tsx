"use client";

import { useState } from "react";
import { fetchApi } from "@/lib/api";
import {
  AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Info,
  Loader2, ShieldCheck, XCircle,
} from "lucide-react";

interface ValidationIssue { level: "error" | "warning" | "info"; code: string; detail: string }
interface ValidationReport {
  doc_id: string; valid: boolean; score: number;
  issues: ValidationIssue[];
  stats: { section_count: number; empty_sections: number; avg_content_len: number; title: string };
}

interface Props { docId: string }

export function ValidationPanel({ docId }: Props) {
  const [showVal,    setShowVal]    = useState(false);
  const [validating, setValidating] = useState(false);
  const [valReport,  setValReport]  = useState<ValidationReport | null>(null);

  async function run() {
    if (showVal) { setShowVal(false); return; }
    setValidating(true); setValReport(null); setShowVal(true);
    try {
      const data = await fetchApi<ValidationReport>(`/api/documents/${docId}/validate`);
      setValReport(data);
    } finally { setValidating(false); }
  }

  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <button onClick={run}
        className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-medium text-gray-300 hover:text-white hover:bg-gray-900 transition-colors">
        <span className="flex items-center gap-1.5">
          <ShieldCheck size={13} className="text-indigo-400" />
          验证解析质量
          {valReport && (
            <span className={`ml-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
              valReport.valid ? "bg-emerald-900/40 text-emerald-300" : "bg-red-900/40 text-red-300"
            }`}>
              {valReport.valid ? "通过" : "有问题"} · {valReport.score}分
            </span>
          )}
        </span>
        {validating ? <Loader2 size={11} className="animate-spin text-gray-500" /> :
          showVal ? <ChevronUp size={11} className="text-gray-500" /> : <ChevronDown size={11} className="text-gray-500" />}
      </button>

      {showVal && (
        <div className="px-3 pb-3 pt-1 border-t border-gray-800 space-y-2">
          {validating && (
            <div className="flex items-center gap-2 text-xs text-gray-500 py-2">
              <Loader2 size={11} className="animate-spin" />验证中...
            </div>
          )}
          {valReport && !validating && (
            <>
              <div className="grid grid-cols-3 gap-2 text-center py-1">
                {[
                  { label: "章节数",   value: valReport.stats.section_count },
                  { label: "空章节",   value: valReport.stats.empty_sections },
                  { label: "平均字数", value: valReport.stats.avg_content_len },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-gray-900 rounded px-2 py-1.5">
                    <div className="text-sm font-mono font-medium text-gray-200">{value}</div>
                    <div className="text-[10px] text-gray-500">{label}</div>
                  </div>
                ))}
              </div>
              {valReport.issues.length === 0 ? (
                <div className="flex items-center gap-1.5 text-xs text-emerald-400 py-1">
                  <CheckCircle2 size={12} />无问题，解析质量良好
                </div>
              ) : (
                <div className="space-y-1">
                  {valReport.issues.map((issue, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      {issue.level === "error"   && <XCircle       size={11} className="text-red-400 mt-0.5 shrink-0" />}
                      {issue.level === "warning" && <AlertTriangle  size={11} className="text-amber-400 mt-0.5 shrink-0" />}
                      {issue.level === "info"    && <Info           size={11} className="text-blue-400 mt-0.5 shrink-0" />}
                      <span className="text-gray-400 leading-snug">{issue.detail}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
