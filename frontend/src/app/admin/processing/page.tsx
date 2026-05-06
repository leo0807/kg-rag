"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw, AlertCircle, CheckCircle2, Clock, RotateCcw, Trash2, PauseCircle } from "lucide-react";
import { fetchApi } from "@/lib/api";

interface ActiveTask {
  task_id: string;
  doc_id: string;
  stage: string;
  progress: number;
  started_at: string;
  elapsed_seconds: number;
  stages_completed: string[];
  stages_pending: string[];
}

interface RecentError {
  task_id: string;
  doc_id: string;
  stage: string;
  error: string;
  timestamp: string;
}

interface ProcessingStatus {
  active_tasks: ActiveTask[];
  queue_size: number;
  completed_today: number;
  failed_today: number;
  recent_errors: RecentError[];
}

const STAGE_SHORT: Record<string, string> = {
  "解析章节": "解析",
  "向量化": "向量",
  "写入Neo4j": "Neo4j",
  "ES索引": "ES",
};

function StageIndicator({ stages_completed, stage }: Pick<ActiveTask, "stages_completed" | "stage">) {
  const all = ["解析章节", "向量化", "写入Neo4j", "ES索引"];
  return (
    <div className="flex gap-1 flex-wrap mt-1">
      {all.map((s) => {
        const done = stages_completed.includes(s);
        const active = stage === s || (stage.startsWith("失败") && s === stage.replace("失败: ", ""));
        return (
          <span
            key={s}
            className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
              done ? "bg-green-500/20 text-green-400"
              : active ? "bg-blue-500/20 text-blue-400 animate-pulse"
              : "bg-white/5 text-gray-500"
            }`}
          >
            {done ? "✓" : active ? "◎" : "◯"} {STAGE_SHORT[s] ?? s}
          </span>
        );
      })}
    </div>
  );
}

export default function ProcessingDashboard() {
  const [status, setStatus] = useState<ProcessingStatus | null>(null);
  const [paused, setPaused] = useState(false);
  const [retrying, setRetrying] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchApi<ProcessingStatus>("/api/admin/processing/status");
      setStatus(data);
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    if (paused) return;
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [paused, refresh]);

  async function handleRetry(task_id: string) {
    setRetrying(task_id);
    try {
      await fetchApi(`/api/admin/processing/retry/${task_id}`, { method: "POST" });
      await refresh();
    } finally {
      setRetrying(null);
    }
  }

  async function handleClear() {
    await fetchApi("/api/admin/processing/clear-completed", { method: "POST" });
    await refresh();
  }

  return (
    <main className="p-6 max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          数据处理看板
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => setPaused((v) => !v)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors hover:bg-white/5"
            style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}
          >
            <PauseCircle size={13} />
            {paused ? "恢复刷新" : "暂停刷新"}
          </button>
          <button
            onClick={handleClear}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors hover:bg-white/5"
            style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}
          >
            <Trash2 size={13} /> 清除已完成
          </button>
          <button
            onClick={refresh}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors hover:bg-white/5"
            style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}
          >
            <RefreshCw size={13} /> 刷新
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "今日完成", value: status?.completed_today ?? 0, icon: <CheckCircle2 size={16} className="text-green-400" /> },
          { label: "今日失败", value: status?.failed_today ?? 0, icon: <AlertCircle size={16} className="text-red-400" /> },
          { label: "等待队列", value: status?.queue_size ?? 0, icon: <Clock size={16} className="text-yellow-400" /> },
        ].map(({ label, value, icon }) => (
          <div key={label} className="rounded-xl border p-4 flex items-center gap-3"
               style={{ borderColor: "var(--border)", background: "var(--card-bg)" }}>
            {icon}
            <div>
              <div className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>{value}</div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Active Tasks */}
      <section>
        <h2 className="text-sm font-medium mb-3" style={{ color: "var(--text-muted)" }}>当前处理中</h2>
        {!status?.active_tasks?.length ? (
          <div className="text-sm text-center py-6 rounded-xl border"
               style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}>
            暂无进行中的任务
          </div>
        ) : (
          <div className="space-y-3">
            {status.active_tasks.map((task) => (
              <div key={task.task_id} className="rounded-xl border p-4"
                   style={{ borderColor: "var(--border)", background: "var(--card-bg)" }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                    {task.doc_id}
                  </span>
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {task.elapsed_seconds}s
                  </span>
                </div>
                {/* Progress bar */}
                <div className="h-2 rounded-full overflow-hidden mb-2" style={{ background: "var(--border)" }}>
                  <div
                    className="h-full rounded-full transition-all duration-500 bg-blue-500"
                    style={{ width: `${task.progress}%` }}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    当前阶段：{task.stage}  {task.progress}%
                  </span>
                </div>
                <StageIndicator {...task} />
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent Errors */}
      <section>
        <h2 className="text-sm font-medium mb-3" style={{ color: "var(--text-muted)" }}>最近错误</h2>
        {!status?.recent_errors?.length ? (
          <div className="text-sm text-center py-6 rounded-xl border"
               style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}>
            暂无错误记录
          </div>
        ) : (
          <div className="space-y-2">
            {status.recent_errors.map((err, i) => (
              <div key={i} className="rounded-lg border p-3 flex items-start justify-between gap-3"
                   style={{ borderColor: "var(--border)", background: "var(--card-bg)" }}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <AlertCircle size={12} className="text-red-400 flex-shrink-0" />
                    <span className="font-mono text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                      {err.doc_id}
                    </span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">
                      {err.stage}
                    </span>
                    <span className="text-xs ml-auto" style={{ color: "var(--text-muted)" }}>
                      {err.timestamp}
                    </span>
                  </div>
                  <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>{err.error}</p>
                </div>
                <button
                  onClick={() => handleRetry(err.task_id)}
                  disabled={retrying === err.task_id}
                  className="flex-shrink-0 flex items-center gap-1 text-xs px-2 py-1 rounded border transition-colors hover:bg-white/5 disabled:opacity-50"
                  style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
                >
                  <RotateCcw size={11} />
                  {retrying === err.task_id ? "..." : "重试"}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
