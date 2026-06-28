"use client";

import { useEffect, useState, useCallback } from "react";
import { RefreshCw, AlertCircle, CheckCircle2, Clock, RotateCcw, Trash2, PauseCircle, Activity } from "lucide-react";
import { fetchApi } from "@/lib/api";

interface ActiveTask {
  task_id: string; doc_id: string; stage: string; progress: number;
  started_at: string; elapsed_seconds: number;
  stages_completed: string[]; stages_pending: string[];
}

interface RecentError {
  task_id: string; doc_id: string; stage: string;
  error: string; timestamp: string;
}

interface ProcessingStatus {
  active_tasks: ActiveTask[]; queue_size: number;
  completed_today: number; failed_today: number; recent_errors: RecentError[];
}

const STAGE_ALL = ["解析章节", "向量化", "写入Neo4j", "ES索引"];
const STAGE_SHORT: Record<string, string> = {
  "解析章节": "解析", "向量化": "向量", "写入Neo4j": "Neo4j", "ES索引": "ES",
};

function StageBar({ stages_completed, stage }: Pick<ActiveTask, "stages_completed" | "stage">) {
  return (
    <div className="flex gap-1.5 mt-2 flex-wrap">
      {STAGE_ALL.map((s) => {
        const done   = stages_completed.includes(s);
        const active = stage === s;
        return (
          <span key={s} className={`text-[10px] px-2 py-0.5 rounded-full font-mono border transition-colors ${
            done   ? "bg-green-500/15 border-green-500/30 text-green-400" :
            active ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-400 animate-pulse" :
                     "bg-white/3 border-white/8 text-gray-600"
          }`}>
            {done ? "✓ " : active ? "◎ " : "○ "}{STAGE_SHORT[s] ?? s}
          </span>
        );
      })}
    </div>
  );
}

function ProgressBar({ value }: { value: number }) {
  const color = value >= 80 ? "from-green-500 to-emerald-400"
              : value >= 40 ? "from-blue-500 to-cyan-400"
              :               "from-yellow-500 to-amber-400";
  return (
    <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden my-2">
      <div
        className={`h-full rounded-full bg-gradient-to-r ${color} transition-all duration-700`}
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

export default function ProcessingDashboard() {
  const [status, setStatus]   = useState<ProcessingStatus | null>(null);
  const [paused, setPaused]   = useState(false);
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
    } finally { setRetrying(null); }
  }

  async function handleClear() {
    await fetchApi("/api/admin/processing/clear-completed", { method: "POST" });
    await refresh();
  }

  const stats = [
    { label: "今日完成", value: status?.completed_today ?? 0, icon: CheckCircle2, color: "text-green-400", border: "border-green-500/20", bg: "bg-green-500/8" },
    { label: "今日失败", value: status?.failed_today   ?? 0, icon: AlertCircle,   color: "text-red-400",   border: "border-red-500/20",   bg: "bg-red-500/8"   },
    { label: "等待队列", value: status?.queue_size     ?? 0, icon: Clock,         color: "text-yellow-400",border: "border-yellow-500/20", bg: "bg-yellow-500/8"},
  ];

  return (
    <main className="p-6 max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between" style={{ animation: "slide-up-fade 0.55s ease both" }}>
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
            <Activity size={15} className="text-blue-400" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">数据处理看板</h1>
            <p className="text-xs text-gray-500 mt-0.5">实时文档处理进度 · 自动刷新</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setPaused(v => !v)}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              paused ? "bg-amber-500/10 border-amber-500/30 text-amber-400" : "border-gray-700 text-gray-400 hover:bg-white/5"
            }`}>
            <PauseCircle size={13} />{paused ? "恢复刷新" : "暂停刷新"}
          </button>
          <button onClick={handleClear}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-400 hover:bg-white/5 transition-colors">
            <Trash2 size={13} /> 清除已完成
          </button>
          <button onClick={refresh}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-400 hover:bg-white/5 transition-colors">
            <RefreshCw size={13} className={!paused ? "animate-spin [animation-duration:3s]" : ""} /> 刷新
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 stagger-children">
        {stats.map(({ label, value, icon: Icon, color, border, bg }) => (
          <div key={label} className={`rounded-xl border ${border} ${bg} p-4 flex items-center gap-3 tech-card`}>
            <div className={`w-9 h-9 rounded-lg bg-gray-900/60 border ${border} flex items-center justify-center shrink-0`}>
              <Icon size={16} className={color} />
            </div>
            <div>
              <div className={`text-2xl font-bold ${color}`}>{value}</div>
              <div className="text-xs text-gray-500">{label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Active Tasks */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider">当前处理中</h2>
          {(status?.active_tasks?.length ?? 0) > 0 && (
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          )}
        </div>
        {!status?.active_tasks?.length ? (
          <div className="text-sm text-center py-8 rounded-xl border border-gray-800 text-gray-600 bg-gray-900/30">
            暂无进行中的任务
          </div>
        ) : (
          <div className="space-y-3 stagger-children">
            {status.active_tasks.map((task) => (
              <div key={task.task_id} className="rounded-xl border border-gray-800 bg-gray-900/60 p-4 tech-card">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-sm font-medium text-white truncate">{task.doc_id}</span>
                  <span className="text-xs text-gray-500 shrink-0 ml-2">{task.elapsed_seconds}s</span>
                </div>
                <ProgressBar value={task.progress} />
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">当前：{task.stage}</span>
                  <span className="text-xs font-medium text-cyan-400">{task.progress}%</span>
                </div>
                <StageBar stages_completed={task.stages_completed} stage={task.stage} />
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent Errors */}
      <section>
        <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">最近错误</h2>
        {!status?.recent_errors?.length ? (
          <div className="text-sm text-center py-8 rounded-xl border border-gray-800 text-gray-600 bg-gray-900/30">
            暂无错误记录
          </div>
        ) : (
          <div className="space-y-2 animate-rows">
            {status.recent_errors.map((err, i) => (
              <div key={i} className="rounded-lg border border-red-900/30 bg-red-950/20 p-3 flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <AlertCircle size={11} className="text-red-400 shrink-0" />
                    <span className="font-mono text-xs font-medium text-white">{err.doc_id}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/20">{err.stage}</span>
                    <span className="text-[10px] text-gray-600 ml-auto shrink-0">{err.timestamp}</span>
                  </div>
                  <p className="text-xs text-gray-500 truncate">{err.error}</p>
                </div>
                <button onClick={() => handleRetry(err.task_id)} disabled={retrying === err.task_id}
                  className="shrink-0 flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-700 text-gray-400 hover:bg-white/5 disabled:opacity-50 transition-colors">
                  <RotateCcw size={11} />{retrying === err.task_id ? "…" : "重试"}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
