"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
import { fetchApi, getApiBaseUrl, getAuthHeaders } from "@/lib/api";

type RunDetail = {
  id: string; run_name: string; status: string; accuracy: number | null;
  avg_latency_ms: number | null; p95_latency_ms: number | null;
  total_questions: number; completed_questions: number;
  accuracy_by_type: Record<string, number> | null;
  tags: string[]; git_commit: string | null;
  started_at: string | null; completed_at: string | null; created_at: string;
};

type ErrorAnalysis = {
  total_errors: number;
  by_reason: Record<string, number>;
  details: { result_id: string; error_reason: string; confidence: number; suggestions: string[] }[];
};

type Suggestion = {
  id: string; category: string; priority: string; title: string;
  description: string; action_items: string[];
};

type Tab = "summary" | "errors" | "suggestions";

export default function RunDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [errors, setErrors] = useState<ErrorAnalysis | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [tab, setTab] = useState<Tab>("summary");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [reporting, setReporting] = useState(false);

  const loadRun = useCallback(async () => {
    const data = await fetchApi<RunDetail>(`/api/admin/eval/runs/${id}`);
    setRun(data ?? null);
    setLoading(false);
  }, [id]);

  const loadErrors = useCallback(async () => {
    const data = await fetchApi<ErrorAnalysis>(`/api/admin/eval/runs/${id}/error-analysis`);
    setErrors(data ?? null);
  }, [id]);

  const loadSuggestions = useCallback(async () => {
    const data = await fetchApi<Suggestion[]>(`/api/admin/eval/runs/${id}/suggestions`);
    setSuggestions(data ?? []);
  }, [id]);

  useEffect(() => { loadRun(); }, [loadRun]);
  useEffect(() => {
    if (tab === "errors") loadErrors();
    if (tab === "suggestions") loadSuggestions();
  }, [tab, loadErrors, loadSuggestions]);

  const triggerAnalysis = async () => {
    setAnalyzing(true);
    await fetchApi(`/api/admin/eval/runs/${id}/analyze`, { method: "POST" });
    setAnalyzing(false);
    await loadErrors();
  };

  const generateReport = async () => {
    setReporting(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/api/admin/eval/runs/${id}/generate-report?fmt=txt`, {
        method: "POST", headers: await getAuthHeaders(),
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a"); a.href = url; a.download = `report_${id}.txt`; a.click();
        URL.revokeObjectURL(url);
      }
    } finally {
      setReporting(false);
    }
  };

  const PRIORITY_COLOR: Record<string, string> = {
    high: "text-red-400 bg-red-900/30", medium: "text-yellow-400 bg-yellow-900/30", low: "text-gray-400 bg-gray-800",
  };

  if (loading) return <div className="flex-1 bg-gray-950 p-6 text-gray-400">加载中…</div>;
  if (!run) return <div className="flex-1 bg-gray-950 p-6 text-red-400">评测运行不存在</div>;

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/admin/eval" className="text-gray-400 hover:text-gray-200 text-sm">← 评测中心</Link>
          <h1 className="text-xl font-semibold text-white">{run.run_name || run.id.slice(0, 12)}</h1>
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${
            run.status === "completed" ? "bg-green-900/40 text-green-400"
            : run.status === "running" ? "bg-blue-900/40 text-blue-400"
            : "bg-gray-800 text-gray-400"}`}>
            {run.status}
          </span>
        </div>
        <div className="flex gap-2">
          <button onClick={generateReport} disabled={reporting}
            className="px-3 py-1.5 text-sm text-gray-300 border border-gray-700 rounded hover:bg-gray-800 disabled:opacity-50">
            {reporting ? "生成中…" : "导出报告"}
          </button>
          <a href={`/api/admin/eval/runs/${id}/export`}
            className="px-3 py-1.5 text-sm text-gray-300 border border-gray-700 rounded hover:bg-gray-800">
            导出 CSV
          </a>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: "准确率", value: run.accuracy != null ? `${(run.accuracy * 100).toFixed(1)}%` : "—" },
          { label: "平均延迟", value: run.avg_latency_ms != null ? `${run.avg_latency_ms.toFixed(0)}ms` : "—" },
          { label: "P95 延迟", value: run.p95_latency_ms != null ? `${run.p95_latency_ms.toFixed(0)}ms` : "—" },
          { label: "完成 / 总计", value: `${run.completed_questions} / ${run.total_questions}` },
        ].map((s) => (
          <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className="text-2xl font-semibold text-white mt-1">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800">
        {(["summary", "errors", "suggestions"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${
              tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-gray-200"}`}>
            {{ summary: "概要", errors: "错题分析", suggestions: "优化建议" }[t]}
          </button>
        ))}
      </div>

      {tab === "summary" && (
        <div className="space-y-4">
          {run.accuracy_by_type && Object.keys(run.accuracy_by_type).length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-200 mb-3">按题型准确率</h3>
              <div className="space-y-2">
                {Object.entries(run.accuracy_by_type).map(([type, acc]) => (
                  <div key={type} className="flex items-center gap-3">
                    <span className="text-xs text-gray-400 w-20">{type}</span>
                    <div className="flex-1 bg-gray-800 rounded-full h-2">
                      <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${(acc as number) * 100}%` }} />
                    </div>
                    <span className="text-xs text-gray-300 w-12 text-right">{((acc as number) * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2 text-sm">
            {run.tags?.length > 0 && <div><span className="text-gray-500">标签: </span>{run.tags.join(", ")}</div>}
            {run.git_commit && <div><span className="text-gray-500">提交: </span><code className="text-xs">{run.git_commit}</code></div>}
            {run.started_at && <div><span className="text-gray-500">开始: </span>{new Date(run.started_at).toLocaleString("zh-CN")}</div>}
            {run.completed_at && <div><span className="text-gray-500">完成: </span>{new Date(run.completed_at).toLocaleString("zh-CN")}</div>}
          </div>
        </div>
      )}

      {tab === "errors" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={triggerAnalysis} disabled={analyzing}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50">
              {analyzing ? "分析中…" : "重新分析"}
            </button>
          </div>
          {errors && (
            <>
              <p className="text-sm text-gray-400">共 {errors.total_errors} 道错题</p>
              <div className="space-y-2">
                {Object.entries(errors.by_reason ?? {}).sort((a, b) => b[1] - a[1]).map(([reason, cnt]) => (
                  <div key={reason} className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded px-4 py-2.5">
                    <span className="flex-1 text-sm text-gray-300">{reason}</span>
                    <span className="text-sm font-semibold text-white">{cnt}</span>
                    <span className="text-xs text-gray-500">{((cnt / errors.total_errors) * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {tab === "suggestions" && (
        <div className="space-y-3">
          {suggestions.length === 0 && <p className="text-gray-500 text-sm">暂无建议，请先运行错题分析</p>}
          {suggestions.map((s) => (
            <div key={s.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
              <div className="flex items-center gap-2">
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${PRIORITY_COLOR[s.priority] ?? "text-gray-400"}`}>
                  {s.priority}
                </span>
                <span className="text-xs text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">{s.category}</span>
                <span className="text-sm font-medium text-white">{s.title}</span>
              </div>
              <p className="text-sm text-gray-400">{s.description}</p>
              {s.action_items.length > 0 && (
                <ul className="space-y-1 mt-1">
                  {s.action_items.map((item, i) => (
                    <li key={i} className="text-xs text-gray-400 flex gap-2">
                      <span className="text-blue-500 shrink-0">•</span>{item}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
