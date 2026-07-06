"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Play, Loader2, CheckCircle2, XCircle } from "lucide-react";

interface Props {
  defaultDocId?: string;
  defaultChapter?: string;
  onComplete?: (graphId: string) => void;
}

interface JobStatus {
  status: "pending" | "running" | "completed" | "failed";
  progress?: number;
  total?: number;
  message?: string;
  graph_id?: string;
}

export function GeneratePanel({ defaultDocId = "", defaultChapter = "2", onComplete }: Props) {
  const [docId,    setDocId]    = useState(defaultDocId);
  const [chapter,  setChapter]  = useState(defaultChapter);
  const [jobId,    setJobId]    = useState<string | null>(null);
  const [job,      setJob]      = useState<JobStatus | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Sync inputs when parent passes a new graph selection
  useEffect(() => { if (defaultDocId) setDocId(defaultDocId); }, [defaultDocId]);
  useEffect(() => { if (defaultChapter) setChapter(defaultChapter); }, [defaultChapter]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
  }, []);

  const startPolling = useCallback((id: string) => {
    stopPolling();
    pollingRef.current = setInterval(async () => {
      try {
        const s = await fetchApi<JobStatus>(`/api/graph/spo/jobs/${id}`);
        setJob(s);
        if (s.status === "completed") {
          stopPolling();
          if (s.graph_id) onComplete?.(s.graph_id);
        } else if (s.status === "failed") {
          stopPolling();
        }
      } catch { stopPolling(); }
    }, 1500);
  }, [stopPolling, onComplete]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  async function handleGenerate() {
    if (!docId.trim()) return;
    setJob({ status: "pending", message: "提交任务…" });
    try {
      const res = await fetchApi<{ graph_id: string; status: string }>(
        "/api/graph/spo/generate", { method: "POST", body: JSON.stringify({ doc_id: docId.trim(), chapter: chapter.trim() || "2" }) }
      );
      setJobId(res.graph_id);
      setJob({ status: "pending", message: "任务已提交，等待处理…" });
      startPolling(res.graph_id);
    } catch (e: unknown) {
      setJob({ status: "failed", message: String(e) });
    }
  }

  const busy = job && (job.status === "pending" || job.status === "running");
  const pct  = job?.total ? Math.round(((job.progress ?? 0) / job.total) * 100) : null;

  return (
    <div className="border-t border-gray-800 bg-gray-900/80 px-4 py-3 space-y-3">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">生成新图谱</p>

      <div className="flex gap-2">
        <div className="flex-1">
          <label className="block text-[10px] text-gray-500 mb-1">文档 ID</label>
          <input
            value={docId}
            onChange={e => setDocId(e.target.value)}
            placeholder="例：GB_T_15834"
            className="w-full bg-gray-800 border border-gray-700 rounded-md px-2.5 py-1.5 text-xs text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-600 focus:ring-1 focus:ring-indigo-600"
          />
        </div>
        <div className="w-24">
          <label className="block text-[10px] text-gray-500 mb-1">章节</label>
          <input
            value={chapter}
            onChange={e => setChapter(e.target.value)}
            placeholder="2 / ALL"
            className="w-full bg-gray-800 border border-gray-700 rounded-md px-2.5 py-1.5 text-xs text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-600 focus:ring-1 focus:ring-indigo-600"
          />
        </div>
      </div>

      <button
        type="button"
        onClick={handleGenerate}
        disabled={!!busy || !docId.trim()}
        className="flex items-center gap-2 w-full justify-center px-3 py-1.5 rounded-md bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-medium text-white transition-colors"
      >
        {busy ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
        {busy ? "生成中…" : "开始生成"}
      </button>

      {job && (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            {job.status === "completed" && <CheckCircle2 size={12} className="text-emerald-400 shrink-0" />}
            {job.status === "failed"    && <XCircle      size={12} className="text-red-400 shrink-0" />}
            {(job.status === "pending" || job.status === "running") && (
              <Loader2 size={12} className="animate-spin text-indigo-400 shrink-0" />
            )}
            <span className={`text-[10px] truncate ${
              job.status === "completed" ? "text-emerald-400"
              : job.status === "failed" ? "text-red-400"
              : "text-gray-400"
            }`}>{job.message}</span>
          </div>
          {pct !== null && job.status === "running" && (
            <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-indigo-500 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
            </div>
          )}
          {job.status === "completed" && jobId && (
            <p className="text-[9px] text-gray-600 font-mono truncate">{jobId}</p>
          )}
        </div>
      )}
    </div>
  );
}
