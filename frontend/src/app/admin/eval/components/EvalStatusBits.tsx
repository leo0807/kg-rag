"use client";

import { pct } from "../types";

export function StatCard({
  label,
  value,
  compact = false,
  tone = "default",
}: {
  label: string;
  value: string;
  compact?: boolean;
  tone?: "default" | "emerald" | "rose";
}) {
  const toneClass =
    tone === "emerald"
      ? "text-emerald-400"
      : tone === "rose"
        ? "text-rose-400"
        : "text-white";

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`mt-1 ${compact ? "text-sm" : "text-lg"} ${toneClass}`}>{value}</div>
    </div>
  );
}

export function MetricCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "emerald";
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`mt-1 text-lg ${tone === "emerald" ? "text-emerald-400" : "text-white"}`}>
        {value}
      </div>
    </div>
  );
}

export function ProgressBar({
  label = "进度",
  current,
  total,
  value,
}: {
  label?: string;
  current: number;
  total: number;
  value: number;
}) {
  return (
    <div>
      <div className="mb-2 flex justify-between text-xs text-gray-500">
        <span>{label}</span>
        <span>
          {current}/{total}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-800">
        <div className="h-full bg-indigo-500 transition-all" style={{ width: pct(value) }} />
      </div>
    </div>
  );
}
