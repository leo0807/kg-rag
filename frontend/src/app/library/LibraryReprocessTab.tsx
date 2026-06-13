"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2, FolderSync, Loader2, Pause, Play, StopCircle, Trash2,
} from "lucide-react";
import { fetchApi } from "@/lib/api";
import { useReprocess } from "./useReprocess";
import { ReprocessOptions } from "./ReprocessOptions";
import { ReprocessProgress } from "./ReprocessProgress";

interface BackfillStatus {
  status: "idle" | "running" | "paused" | "completed";
  total: number; done: number; current_doc: string;
  percent: number; elapsed_seconds: number; estimated_remaining_seconds: number;
}

function fmtRemaining(secs: number): string {
  if (secs <= 0) return "";
  if (secs < 60) return "约 1 分钟";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `约 ${mins} 分钟`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem > 0 ? `约 ${hrs} 小时 ${rem} 分钟` : `约 ${hrs} 小时`;
}

function BackfillCard({ isAdmin }: { isAdmin: boolean }) {
  const [bf, setBf] = useState<BackfillStatus | null>(null);
  const [bfBusy, setBfBusy] = useState(false);
  const [stopConfirm, setStopConfirm] = useState(false);
  const bfPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchBf() {
    try {
      const data = await fetchApi<BackfillStatus>("/api/documents/backfill/status");
      setBf(data);
    } catch {}
  }

  useEffect(() => { fetchBf(); }, []);
  useEffect(() => {
    if (bfPollRef.current) clearInterval(bfPollRef.current);
    if (bf?.status === "running" || bf?.status === "paused") {
      bfPollRef.current = setInterval(fetchBf, 3000);
    }
    return () => { if (bfPollRef.current) clearInterval(bfPollRef.current); };
  }, [bf?.status]);

  async function bfStart() {
    setBfBusy(true);
    try {
      const data = await fetchApi<BackfillStatus>("/api/documents/backfill/start", { method: "POST" });
      setBf(data);
    } finally { setBfBusy(false); fetchBf(); }
  }

  async function bfTogglePause() {
    if (!bf) return;
    setBfBusy(true);
    try {
      const ep = bf.status === "running" ? "/api/documents/backfill/pause" : "/api/documents/backfill/resume";
      await fetchApi(ep, { method: "POST" });
    } finally { setBfBusy(false); fetchBf(); }
  }

  async function bfStop() {
    setStopConfirm(false); setBfBusy(true);
    try {
      await fetchApi("/api/documents/backfill/stop", { method: "POST" });
      setBf(s => s ? { ...s, status: "idle" } : s);
    } finally { setBfBusy(false); fetchBf(); }
  }

  const isRunning = bf?.status === "running";
  const isPaused = bf?.status === "paused";
  const isActive = isRunning || isPaused;
  const isDone = bf?.status === "completed";
  const pct = Math.min(100, Math.max(0, bf?.percent ?? 0));

  return (
    <>
      <div className="bg-gray-950 border border-gray-800 rounded-xl p-4 mb-1">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <FolderSync size={14} className={isRunning ? "text-indigo-400" : "text-gray-500"} />
            <span className="text-sm font-medium text-white">图片补全任务</span>
            {isRunning && <span className="px-1.5 py-0.5 bg-amber-900/40 text-amber-300 text-xs rounded-full font-medium">运行中</span>}
            {isPaused && <span className="px-1.5 py-0.5 bg-gray-700 text-gray-300 text-xs rounded-full font-medium">已暂停</span>}
            {isDone && <span className="px-1.5 py-0.5 bg-emerald-900/40 text-emerald-300 text-xs rounded-full font-medium">已完成</span>}
          </div>
          {isAdmin && (
            <div className="flex items-center gap-2">
              {!isActive && !isDone && (
                <button onClick={bfStart} disabled={bfBusy}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                             bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors">
                  {bfBusy ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}启动任务
                </button>
              )}
              {isActive && (
                <>
                  <button onClick={bfTogglePause} disabled={bfBusy}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                               border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 disabled:opacity-50 transition-colors">
                    {bfBusy ? <Loader2 size={11} className="animate-spin" /> : isRunning ? <Pause size={11} /> : <Play size={11} />}
                    {isRunning ? "暂停" : "恢复"}
                  </button>
                  <button onClick={() => setStopConfirm(true)} disabled={bfBusy}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                               border border-red-700/60 text-red-400 hover:bg-red-900/20 disabled:opacity-50 transition-colors">
                    <StopCircle size={11} />停止
                  </button>
                </>
              )}
              {isDone && (
                <button onClick={() => setBf(s => s ? { ...s, status: "idle" } : s)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                             border border-gray-700 text-gray-500 hover:text-gray-300 transition-colors">
                  <Trash2 size={11} />清除
                </button>
              )}
            </div>
          )}
        </div>
        {!isActive && !isDone && <p className="text-xs text-gray-500 mb-2">将所有未建立图像节点的文档逐份提取图片并上传至知识图谱</p>}
        {isActive && (
          <div className="mt-2 space-y-2">
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              {isRunning && pct === 0
                ? <div className="h-full w-full bg-indigo-500/40 animate-pulse rounded-full" />
                : <div className={`h-full rounded-full transition-all duration-500 ${isRunning ? "bg-indigo-500" : "bg-gray-600"}`}
                    style={{ width: `${pct}%`, minWidth: pct > 0 ? "4px" : "0" }} />
              }
            </div>
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>
                {bf?.current_doc && <span className="font-mono text-indigo-400 mr-2">{bf.current_doc}</span>}
                已处理&nbsp;<span className={isRunning ? "text-indigo-300" : "text-gray-300"}>{bf?.done ?? 0}</span>&nbsp;/&nbsp;{bf?.total ?? "—"} 份文档
                <span className="ml-1.5 text-gray-600">({pct.toFixed(1)}%)</span>
              </span>
              {(bf?.estimated_remaining_seconds ?? 0) > 0 && isRunning && (
                <span>预计剩余：{fmtRemaining(bf!.estimated_remaining_seconds)}</span>
              )}
            </div>
          </div>
        )}
        {isDone && <div className="flex items-center gap-2 text-sm text-emerald-400 mt-1"><CheckCircle2 size={14} />全部 {bf?.total} 份文档图片已补全</div>}
        {!isAdmin && !isActive && !isDone && <p className="text-xs text-gray-600 mt-1">当前无图片补全任务在运行</p>}
      </div>
      {stopConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setStopConfirm(false)}>
          <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 w-96 shadow-2xl" onClick={e => e.stopPropagation()}>
            <h2 className="text-base font-semibold text-white mb-2">确认停止图片补全任务？</h2>
            <p className="text-sm text-gray-400 mb-5">下次需要手动重新启动。已处理的图片数据不会丢失，下次启动时只会处理仍未补全的文档。</p>
            <div className="flex gap-3">
              <button onClick={() => setStopConfirm(false)} className="flex-1 py-2 rounded-lg border border-gray-700 text-sm text-gray-400 hover:text-white transition-colors">取消</button>
              <button onClick={bfStop} className="flex-1 py-2 rounded-lg bg-red-700 text-white text-sm font-medium hover:bg-red-600 transition-colors">确认停止</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function LibraryReprocessTab({ isAdmin = true }: { isAdmin?: boolean }) {
  const {
    sel, setSel, docs, docsLoading, docSearch, setDocSearch,
    selectedDocs, filteredDocs, allSelected, someSelected,
    batch, busy, confirm, setConfirm,
    toggleDoc, toggleAll, clearSelection, start, cancel, resume, clearBatch,
  } = useReprocess();

  const isRunning = batch.status === "running";
  const isDone = ["completed", "cancelled", "failed", "interrupted"].includes(batch.status);
  const canResume = isDone && (batch.completed_docs?.length ?? 0) < (batch.total ?? 0) && batch.status !== "completed";

  return (
    <div className="space-y-5 w-full">
      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
        选择待处理文档（不选则处理全部），勾选管道后点击"批量处理"启动任务。运行期间可在此查看进度和错误详情。
      </div>
      <BackfillCard isAdmin={isAdmin} />
      <ReprocessOptions
        sel={sel} setSel={setSel} docs={docs} docsLoading={docsLoading}
        docSearch={docSearch} setDocSearch={setDocSearch}
        selectedDocs={selectedDocs} filteredDocs={filteredDocs}
        allSelected={allSelected} someSelected={someSelected}
        isRunning={isRunning} isDone={isDone} canResume={canResume}
        busy={busy} confirm={confirm} setConfirm={setConfirm}
        toggleDoc={toggleDoc} toggleAll={toggleAll} clearSelection={clearSelection}
        start={start} cancel={cancel} resume={resume} clearBatch={clearBatch}
      />
      <ReprocessProgress batch={batch} />
    </div>
  );
}
