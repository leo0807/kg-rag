"use client";

import { Loader2, RotateCcw } from "lucide-react";

interface Snapshot {
  snapshot_id: string; timestamp: number;
  constraints_count: number; defects_count: number; images_count: number;
}

interface Props {
  snapshots: Snapshot[];
  isRunning: boolean;
  rolling: boolean;
  rollTarget: string;
  onSelectTarget: (id: string) => void;
  onRollback: () => void;
}

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleString("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

export function SnapshotRollback({ snapshots, isRunning, rolling, rollTarget, onSelectTarget, onRollback }: Props) {
  if (snapshots.length === 0) return null;
  return (
    <div className="border border-gray-800 rounded-lg p-3 space-y-2">
      <div className="text-xs text-gray-500 uppercase tracking-wider">回滚到历史快照</div>
      <select value={rollTarget} onChange={e => onSelectTarget(e.target.value)}
        className="w-full px-2.5 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500">
        <option value="">— 选择快照 —</option>
        {snapshots.map(s => (
          <option key={s.snapshot_id} value={s.snapshot_id}>
            {fmtTime(s.timestamp)} · 约束 {s.constraints_count} · 图纸 {s.images_count} · 缺陷 {s.defects_count}
          </option>
        ))}
      </select>
      <button onClick={onRollback} disabled={!rollTarget || rolling || isRunning}
        className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium border border-amber-700 text-amber-400 hover:bg-amber-900/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
        {rolling ? <Loader2 size={11} className="animate-spin" /> : <RotateCcw size={11} />}
        执行回滚
      </button>
    </div>
  );
}
