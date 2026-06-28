"use client";

import { fetchApi } from "@/lib/api";
import { FileText, Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { GenerationTask, STATUS_COLORS, STATUS_LABELS } from "./types";

export default function GenerationPage() {
  const [tasks, setTasks]     = useState<GenerationTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter]   = useState<string>("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const url = filter === "all"
        ? "/api/generation/tasks"
        : `/api/generation/tasks?status=${filter}`;
      const d = await fetchApi<{ items: GenerationTask[] }>(url);
      setTasks(d.items);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const FILTERS = [
    { key: "all",      label: "全部" },
    { key: "pending",  label: "待启动" },
    { key: "running",  label: "生成中" },
    { key: "done",     label: "已完成" },
    { key: "finalized",label: "已定稿" },
    { key: "failed",   label: "失败" },
  ];

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
            <FileText size={18} className="text-indigo-400" />
            规范自动生成
          </h1>
          <div className="flex items-center gap-2">
            <button onClick={load} disabled={loading}
              className="p-1.5 text-gray-500 hover:text-gray-300 disabled:opacity-40">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
            <Link href="/generation/new"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded-lg transition-colors">
              <Plus size={13} /> 新建任务
            </Link>
          </div>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 mb-4 bg-gray-900 border border-gray-800 rounded-lg p-0.5 w-fit">
          {FILTERS.map(f => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={`px-3 py-1 rounded text-xs transition-colors ${
                filter === f.key
                  ? "bg-indigo-600 text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}>
              {f.label}
            </button>
          ))}
        </div>

        {/* Empty state */}
        {!loading && tasks.length === 0 && (
          <div className="flex flex-col items-center justify-center min-h-48 gap-3 text-gray-600">
            <FileText size={32} className="opacity-30" />
            <p className="text-sm">暂无生成任务</p>
            <Link href="/generation/new"
              className="text-xs text-indigo-400 hover:text-indigo-300 underline underline-offset-2">
              创建第一个任务
            </Link>
          </div>
        )}

        {/* Task grid */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 stagger-children">
          {tasks.map(task => (
            <TaskCard key={task.id} task={task} onDelete={() => load()} />
          ))}
        </div>
      </div>
    </div>
  );
}

function TaskCard({ task, onDelete }: { task: GenerationTask; onDelete: () => void }) {
  const href = task.status === "done" || task.status === "finalized"
    ? `/generation/${task.id}/edit`
    : `/generation/${task.id}`;

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (!confirm(`删除任务"${task.task_name}"？`)) return;
    try {
      await fetchApi(`/api/generation/tasks/${task.id}`, { method: "DELETE" });
      onDelete();
    } catch { /* silent */ }
  };

  return (
    <Link href={href}
      className="block bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-indigo-700 transition-colors group tech-card">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-sm font-medium text-gray-100 line-clamp-1 flex-1">
          {task.task_name}
        </span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded shrink-0 ${STATUS_COLORS[task.status] ?? ""}`}>
          {STATUS_LABELS[task.status] ?? task.status}
        </span>
      </div>

      <div className="text-xs text-gray-500 mb-3">
        {task.spec_type} &nbsp;·&nbsp;
        {task.created_at?.slice(0, 10)}
      </div>

      {task.status === "running" && (
        <div className="mb-3">
          <div className="flex justify-between text-[10px] text-gray-500 mb-1">
            <span>{task.current_step}</span>
            <span>{task.progress}%</span>
          </div>
          <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
            <div className="h-full bg-indigo-500 rounded-full transition-all"
              style={{ width: `${task.progress}%` }} />
          </div>
        </div>
      )}

      {task.validation_report && (
        <div className="text-[10px] text-gray-600">
          质量评分：
          <span className={
            (task.validation_report.overall_score ?? 0) >= 80
              ? "text-green-400"
              : "text-amber-400"
          }>
            {task.validation_report.overall_score}
          </span>
        </div>
      )}

      <div className="mt-3 flex justify-end">
        <button onClick={handleDelete}
          className="text-[10px] text-gray-700 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity">
          删除
        </button>
      </div>
    </Link>
  );
}
