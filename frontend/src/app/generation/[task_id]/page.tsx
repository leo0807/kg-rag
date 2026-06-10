"use client";

import { fetchApi } from "@/lib/api";
import { ArrowLeft, Edit3 } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";
import type { GenerationTask } from "../types";
import { ProgressPanel } from "./ProgressPanel";
import { SectionPreview } from "./SectionPreview";

interface Props { params: Promise<{ task_id: string }> }

export default function TaskProgressPage({ params }: Props) {
  const { task_id } = use(params);
  const [task, setTask]   = useState<GenerationTask | null>(null);
  const [loading, setLoading] = useState(true);
  const eventSourceRef    = useRef<EventSource | null>(null);

  const load = async () => {
    try {
      const t = await fetchApi<GenerationTask>(`/api/generation/tasks/${task_id}`);
      setTask(t);
      return t;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  };

  // Polling via SSE when running
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task_id]);

  useEffect(() => {
    if (!task) return;
    if (task.status !== "running" && task.status !== "pending") return;

    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const url = `${window.location.protocol}//${window.location.hostname}:8000` +
      `/api/generation/tasks/${task_id}/stream` +
      (token ? `?token=${encodeURIComponent(token)}` : "");

    // SSE doesn't support auth headers — fall back to polling
    const interval = setInterval(async () => {
      const t = await load();
      if (t && t.status !== "running" && t.status !== "pending") {
        clearInterval(interval);
      }
    }, 3000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task?.status]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-950">
        <p className="text-xs text-gray-500">加载中…</p>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-950">
        <p className="text-xs text-red-400">任务不存在</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-3xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/generation" className="text-gray-600 hover:text-gray-400">
              <ArrowLeft size={16} />
            </Link>
            <div>
              <h1 className="text-base font-semibold text-gray-100">{task.task_name}</h1>
              <p className="text-xs text-gray-500">{task.spec_type} · {task.created_at?.slice(0, 10)}</p>
            </div>
          </div>

          {(task.status === "done" || task.status === "finalized") && (
            <Link href={`/generation/${task_id}/edit`}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded-lg">
              <Edit3 size={12} /> 进入编辑器
            </Link>
          )}
        </div>

        {/* Progress */}
        <ProgressPanel task={task} />

        {/* Section preview */}
        {task.result_sections && Object.keys(task.result_sections).length > 0 && (
          <SectionPreview sections={task.result_sections} />
        )}

        {/* Validation report summary */}
        {task.validation_report && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-300">自检报告</span>
              <span className={`text-sm font-semibold ${
                (task.validation_report.overall_score ?? 0) >= 80
                  ? "text-green-400" : "text-amber-400"
              }`}>
                {task.validation_report.overall_score} 分
              </span>
            </div>
            {task.validation_report.suggestions?.map((s, i) => (
              <p key={i} className="text-xs text-gray-500 mt-1">· {s}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
