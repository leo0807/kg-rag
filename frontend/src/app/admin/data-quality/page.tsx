"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { AlertTriangle, CheckCircle, RefreshCw } from "lucide-react";

type Issue = { type: string; severity: "high" | "medium" | "low"; count: number; message: string };
type Summary = {
  checked_at: string; total_issues: number;
  severity_counts: { high: number; medium: number; low: number };
  issues: Issue[];
};

const SEV_STYLE: Record<string, string> = {
  high:   "bg-red-500/15 text-red-400 border-red-500/30",
  medium: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  low:    "bg-blue-500/15 text-blue-400 border-blue-500/30",
};
const SEV_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };

export default function DataQualityPage() {
  const [data, setData] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    const d = await fetchApi<Summary>("/api/admin/data-quality/summary");
    if (d) setData(d);
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className="flex-1 overflow-y-auto bg-gray-950 p-5 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <AlertTriangle size={20} className="text-yellow-400" /> 数据质量
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">文档与图谱质量检查</p>
        </div>
        <button onClick={refresh} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-700 text-gray-300 text-sm rounded hover:bg-gray-800 disabled:opacity-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> 刷新
        </button>
      </div>

      {data && (
        <>
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-gray-900 rounded-lg p-4 col-span-1">
              <p className="text-xs text-gray-500">检查时间</p>
              <p className="text-xs text-gray-300 mt-1">
                {new Date(data.checked_at).toLocaleString("zh-CN")}
              </p>
            </div>
            {(["high", "medium", "low"] as const).map((s) => (
              <div key={s} className="bg-gray-900 rounded-lg p-4">
                <p className="text-xs text-gray-500">{SEV_LABEL[s]}风险</p>
                <p className={`text-2xl font-bold mt-1 ${s === "high" ? "text-red-400" : s === "medium" ? "text-yellow-400" : "text-blue-400"}`}>
                  {data.severity_counts[s]}
                </p>
              </div>
            ))}
          </div>

          {data.total_issues === 0 ? (
            <div className="bg-green-900/20 border border-green-700/30 rounded-lg p-6 text-center">
              <CheckCircle size={32} className="text-green-400 mx-auto mb-2" />
              <p className="text-green-400 font-medium">数据质量检查通过</p>
              <p className="text-sm text-gray-500 mt-1">未发现质量问题</p>
            </div>
          ) : (
            <div className="space-y-2">
              {data.issues.map((issue) => (
                <div key={issue.type} className={`flex items-center justify-between p-4 rounded-lg border ${SEV_STYLE[issue.severity]}`}>
                  <div>
                    <p className="text-sm font-medium">{issue.message}</p>
                    <p className="text-xs opacity-70 mt-0.5 font-mono">{issue.type}</p>
                  </div>
                  <span className="text-lg font-bold">{issue.count}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
