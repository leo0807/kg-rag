"use client";

export type StreamPhase = "idle" | "searching" | "generating" | "done";

export interface StreamStage {
  name: "classify" | "retrieve" | "rerank" | "reason" | "validate" | "done";
  label: string;
  progress: number;
}

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
  stage?: StreamStage | null;
  retrievedCount?: number | null;
}

export function ProgressIndicator({ phase, stage, retrievedCount }: Props) {
  if ((phase === "idle" || phase === "done") && !stage) return null;
  if (stage?.name === "done") return null;
  const progress = stage?.progress ?? (phase === "searching" ? 25 : 65);
  const label =
    stage?.label ??
    PHASE_META[phase as Exclude<StreamPhase, "idle" | "done">]?.label ??
    "正在处理中...";
  const icon =
    stage?.name === "validate"
      ? "✓"
      : stage?.name === "reason" || phase === "generating"
        ? "⚡"
        : "🔍";
  const barWidth =
    progress <= 5
      ? "w-[5%]"
      : progress <= 25
        ? "w-1/4"
        : progress <= 45
          ? "w-[45%]"
          : progress <= 65
            ? "w-2/3"
            : progress <= 95
              ? "w-[95%]"
              : "w-full";

  return (
    <div className="mb-4 rounded-xl border border-indigo-900/30 bg-indigo-950/20 px-4 py-3">
      <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
        <span
          className={
            stage?.name === "reason" || phase === "generating"
              ? "animate-spin"
              : "animate-pulse"
          }
        >
          {icon}
        </span>
        <span className="flex-1">
          {stage?.name === "retrieve" && retrievedCount !== undefined
            ? `✓ 找到 ${retrievedCount} 个相关章节`
            : label}
        </span>
        <span className="ml-auto text-[11px] text-indigo-300/70">
          {progress}%
        </span>
      </div>
      {(stage?.name === "reason" || phase === "generating") && (
        <div className="mt-1 text-[11px] text-indigo-300/70">
          正在整理检索结果并生成答案...
        </div>
      )}
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-indigo-950/40">
        <div
          className={`h-full rounded-full bg-gradient-to-r from-indigo-500 to-cyan-400 ${barWidth}`}
        />
      </div>
    </div>
  );
}
