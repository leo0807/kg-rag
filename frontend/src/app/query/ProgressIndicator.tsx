"use client";

export type StreamPhase = "idle" | "searching" | "generating" | "done";

const PHASE_META: Record<
  Exclude<StreamPhase, "idle" | "done">,
  { icon: string; label: string; percent: string; barClass: string }
> = {
  searching: {
    icon: "🔍",
    label: "正在检索相关规范...",
    percent: "25%",
    barClass: "w-1/4",
  },
  generating: {
    icon: "⚡",
    label: "正在生成答案...",
    percent: "65%",
    barClass: "w-2/3",
  },
};

interface Props {
  phase: StreamPhase;
  retrievedCount?: number | null;
}

export function ProgressIndicator({ phase, retrievedCount }: Props) {
  if (phase === "idle" || phase === "done") return null;
  const meta = PHASE_META[phase];

  return (
    <div className="mb-4 rounded-xl border border-indigo-900/30 bg-indigo-950/20 px-4 py-3">
      <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
        <span
          className={phase === "generating" ? "animate-spin" : "animate-pulse"}
        >
          {meta.icon}
        </span>
        <span>
          {phase === "generating" && retrievedCount !== undefined
            ? `✓ 找到 ${retrievedCount} 个相关章节`
            : meta.label}
        </span>
        <span className="ml-auto text-[11px] text-indigo-300/70">
          {meta.percent}
        </span>
      </div>
      {phase === "generating" && (
        <div className="mt-1 text-[11px] text-indigo-300/70">
          正在整理检索结果并生成答案...
        </div>
      )}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-indigo-950/40">
        <div
          className={`h-full rounded-full bg-gradient-to-r from-indigo-500 to-cyan-400 ${meta.barClass}`}
        />
      </div>
    </div>
  );
}
