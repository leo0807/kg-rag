"use client";

import { AlertCircle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import type { Batch } from "./useReprocess";

interface Props {
  batch: Batch;
}

export function ReprocessProgress({ batch }: Props) {
  const isRunning = batch.status === "running";
  const isDone = ["completed", "cancelled", "failed", "interrupted"].includes(batch.status);
  const progress = batch.total ? Math.round(((batch.done ?? 0) / batch.total) * 100) : 0;
  const activePipelines = batch.pipelines ?? [];
  const stepIdx = activePipelines.indexOf(batch.current_step ?? "");
  const docPct = activePipelines.length > 0 && stepIdx >= 0
    ? Math.round((stepIdx / activePipelines.length) * 100)
    : 0;

  if (batch.status === "idle") return null;

  const statusLabel: Record<string, string> = {
    running: "运行中", completed: "已完成", cancelled: "已中止",
    cancelling: "中止中", interrupted: "已中断(服务重启)", failed: "失败",
  };
  const statusColor: Record<string, string> = {
    running: "bg-amber-900/40 text-amber-300",
    completed: "bg-emerald-900/40 text-emerald-300",
    cancelled: "bg-gray-700 text-gray-300",
    cancelling: "bg-orange-900/40 text-orange-300",
    interrupted: "bg-yellow-900/40 text-yellow-300",
  };

  return (
    <div className="bg-gray-950 border border-gray-800 rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-white">批量任务</span>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor[batch.status] ?? "bg-red-900/40 text-red-300"}`}>
          {statusLabel[batch.status] ?? batch.status}
        </span>
      </div>

      {(isRunning || isDone) && (
        <>
          <div>
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>文档总进度</span>
              <span className="tabular-nums">{batch.done ?? 0} / {batch.total ?? "—"} 个文档&nbsp;({progress}%)</span>
            </div>
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              {isRunning && progress === 0 ? (
                <div className="h-full w-full bg-indigo-500/50 animate-pulse rounded-full" />
              ) : (
                <div className="h-full bg-indigo-500 transition-all duration-700 rounded-full"
                  style={{ width: `${progress}%`, minWidth: progress > 0 ? "6px" : "0" }} />
              )}
            </div>
          </div>

          {isRunning && batch.current_doc && activePipelines.length > 0 && (
            <div>
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span className="font-mono text-indigo-400 truncate max-w-[60%]">{batch.current_doc}</span>
                <span className="tabular-nums">{batch.current_step || "—"}&nbsp;({stepIdx >= 0 ? stepIdx : 0}/{activePipelines.length})</span>
              </div>
              <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-400/60 transition-all duration-500 rounded-full" style={{ width: `${docPct}%` }} />
              </div>
            </div>
          )}
        </>
      )}

      {isRunning && batch.message && (
        <div className="flex items-center gap-1.5 text-xs text-gray-500 pt-0.5">
          <Loader2 size={10} className="animate-spin shrink-0" />
          <span className="italic truncate">{batch.message}</span>
        </div>
      )}

      {isRunning && (
        <div className="text-[10px] text-gray-600 border-t border-gray-800 pt-2 leading-relaxed">
          任务在服务端后台运行，关闭浏览器或退出登录后仍会继续处理。重新登录后可在此查看进度。
        </div>
      )}

      {batch.status === "completed" && (
        <div className="flex items-center gap-2 text-sm text-emerald-400">
          <CheckCircle2 size={15} />全部 {batch.total} 个文档处理完成
        </div>
      )}
      {batch.status === "cancelled" && (
        <div className="text-xs text-gray-400">
          已完成 {batch.completed_docs?.length ?? 0} / {batch.total} 个，点击"续跑"从断点继续
        </div>
      )}

      {(batch.errors?.length ?? 0) > 0 && (
        <div className="space-y-1 pt-1 border-t border-gray-800">
          <div className="flex items-center gap-1.5 text-xs text-red-400 mb-1">
            <AlertCircle size={11} />{batch.errors!.length} 个文档失败
          </div>
          {batch.errors!.slice(0, 8).map((e, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <XCircle size={11} className="text-red-500 mt-0.5 shrink-0" />
              <span className="font-mono text-gray-400 shrink-0">{e.doc_id}</span>
              <span className="text-gray-600 truncate">{e.error}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
