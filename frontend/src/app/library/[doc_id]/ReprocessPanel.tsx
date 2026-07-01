"use client";

import { useState, useEffect, useRef } from "react";
import { fetchApi } from "@/lib/api";
import { RefreshCw, CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp, Square } from "lucide-react";
import { ConfirmReprocessModal } from "./ConfirmReprocessModal";
import { ValidationPanel } from "./ValidationPanel";
import { SnapshotRollback } from "./SnapshotRollback";

const PIPELINES = [
  { key: "reparse",     label: "重新解析章节", desc: "重新从 PDF 提取章节结构（修复 0 章节文档）" },
  { key: "images",      label: "图片补全",     desc: "重新提取图片节点并写入图谱" },
  { key: "entities",    label: "实体提取",     desc: "工具 / 材料 / 工序节点" },
  { key: "constraints", label: "约束参数",     desc: "LLM 提取力矩/公差/温度约束" },
  { key: "tables",      label: "表格提取",     desc: "PP-Structure → Constraint 节点" },
  { key: "drawings",    label: "工程图纸",     desc: "VLM 重新分析尺寸标注与装配关系" },
  { key: "defects",     label: "缺陷检测",     desc: "YOLOv11 视觉质检" },
] as const;
type PK = typeof PIPELINES[number]["key"];

interface Snapshot { snapshot_id: string; timestamp: number; constraints_count: number; defects_count: number; images_count: number }
interface TaskStatus { status: string; pipelines?: string[]; current?: string; message?: string; results?: Record<string, number>; error?: string; snapshot_id?: string }
interface Props { docId: string; onComplete?: () => void }

export function ReprocessPanel({ docId, onComplete }: Props) {
  const [selected,   setSelected]   = useState<Set<PK>>(new Set<PK>(["images","entities","constraints","tables","drawings"]));
  const [task,       setTask]       = useState<TaskStatus>({ status: "idle" });
  const [snapshots,  setSnapshots]  = useState<Snapshot[]>([]);
  const [busy,       setBusy]       = useState(false);
  const [confirm,    setConfirm]    = useState(false);
  const [showRes,    setShowRes]    = useState(false);
  const [rollTarget, setRollTarget] = useState("");
  const [rolling,    setRolling]    = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function loadSnapshots() {
    fetchApi<{ snapshots: Snapshot[] }>(`/api/documents/${docId}/snapshots`)
      .then(d => setSnapshots(d.snapshots ?? [])).catch(() => {});
  }

  useEffect(() => {
    fetchApi<TaskStatus>(`/api/documents/${docId}/reprocess/status`)
      .then(setTask).catch(() => {});
    loadSnapshots();
  }, [docId]);

  useEffect(() => {
    const active = task.status === "running" || task.status === "pending";
    if (active) {
      pollRef.current = setInterval(async () => {
        const d = await fetchApi<TaskStatus>(`/api/documents/${docId}/reprocess/status`);
        setTask(d);
        if (d.status !== "running" && d.status !== "pending") {
          clearInterval(pollRef.current!);
          setShowRes(true);
          loadSnapshots();
          if (d.status === "completed") onComplete?.();
        }
      }, 2000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [task.status]);

  async function start() {
    setConfirm(false); setBusy(true);
    try {
      const d = await fetchApi<TaskStatus>(`/api/documents/${docId}/reprocess`, {
        method: "POST", body: JSON.stringify({ pipelines: [...selected] }),
      });
      setTask({ status: d.status === "started" ? "pending" : d.status, pipelines: [...selected] });
      setShowRes(false);
    } finally { setBusy(false); }
  }

  async function rollback() {
    if (!rollTarget) return;
    setRolling(true);
    try {
      await fetchApi(`/api/documents/${docId}/rollback/${rollTarget}`, { method: "POST" });
      setRollTarget(""); loadSnapshots();
    } finally { setRolling(false); }
  }

  const isRunning = task.status === "running" || task.status === "pending";
  const isDone    = ["completed","cancelled","failed"].includes(task.status);

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">选择处理管道</div>
        {PIPELINES.map(({ key, label, desc }) => (
          <label key={key}
            className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
              selected.has(key) ? "border-indigo-600/60 bg-indigo-900/20" : "border-gray-800 hover:border-gray-700"
            } ${isRunning ? "opacity-50 pointer-events-none" : ""}`}>
            <input type="checkbox" className="mt-0.5 accent-indigo-500"
              checked={selected.has(key)} disabled={isRunning}
              onChange={() => setSelected(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; })} />
            <div>
              <div className="text-sm text-gray-200 font-medium">{label}</div>
              <div className="text-xs text-gray-500">{desc}</div>
            </div>
          </label>
        ))}
      </div>

      <div className="flex gap-2">
        <button onClick={() => setConfirm(true)} disabled={isRunning || busy || selected.size === 0}
          className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          {isRunning ? <><Loader2 size={13} className="animate-spin" />处理中...</> : <><RefreshCw size={13} />重新处理</>}
        </button>
        {isRunning && (
          <button onClick={() => fetchApi(`/api/documents/${docId}/reprocess/cancel`, { method: "POST" })}
            className="px-3 py-2 rounded-lg text-sm border border-red-700 text-red-400 hover:bg-red-900/20 transition-colors flex items-center gap-1.5">
            <Square size={12} />中止
          </button>
        )}
      </div>

      {isRunning && (
        <div className="px-3 py-2.5 bg-gray-900 border border-gray-800 rounded-lg text-xs">
          <div className="flex items-center gap-2 text-amber-400 mb-1">
            <Loader2 size={11} className="animate-spin" />
            <span className="font-medium">{task.current || "初始化"}</span>
          </div>
          <div className="text-gray-500">{task.message}</div>
        </div>
      )}

      {isDone && task.results && (
        <div className={`border rounded-lg overflow-hidden ${task.status === "completed" ? "border-emerald-800/50" : "border-gray-700"}`}>
          <button onClick={() => setShowRes(v => !v)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium">
            <span className="flex items-center gap-1.5">
              {task.status === "completed" ? <CheckCircle size={12} className="text-emerald-400" /> : <XCircle size={12} className="text-gray-400" />}
              {task.status === "completed" ? "处理完成" : task.status === "cancelled" ? "已中止" : "处理失败"}
            </span>
            {showRes ? <ChevronUp size={12} className="text-gray-500" /> : <ChevronDown size={12} className="text-gray-500" />}
          </button>
          {showRes && (
            <div className="px-3 pb-3 space-y-1">
              {task.error && <div className="text-xs text-red-400 mb-2">{task.error}</div>}
              {Object.entries(task.results).map(([pipe, count]) => (
                <div key={pipe} className="flex justify-between text-xs">
                  <span className="text-gray-400">{PIPELINES.find(p => p.key === pipe)?.label ?? pipe}</span>
                  <span className={`font-mono ${count < 0 ? "text-red-400" : "text-emerald-400"}`}>
                    {count < 0 ? "失败" : `+${count}`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <ValidationPanel docId={docId} />

      <SnapshotRollback snapshots={snapshots} isRunning={isRunning} rolling={rolling}
        rollTarget={rollTarget} onSelectTarget={setRollTarget} onRollback={rollback} />

      {confirm && (
        <ConfirmReprocessModal
          selectedLabels={[...selected].map(k => PIPELINES.find(p => p.key === k)?.label ?? k)}
          onCancel={() => setConfirm(false)} onConfirm={start} />
      )}
    </div>
  );
}
