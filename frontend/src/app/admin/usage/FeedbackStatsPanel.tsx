"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

interface DetailedStats {
  averages: Record<string, number | null>;
  low_score_questions: {
    question: string;
    scores: Record<string, number | null>;
    created_at: string | null;
  }[];
}

const DIM_LABELS: Record<string, string> = {
  retrieval:    "检索准确度",
  completeness: "答案完整性",
  clarity:      "表述清晰度",
  graph:        "图谱关联度",
};

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  const pct = value != null ? ((value - 1) / 4) * 100 : 0;
  const color = value == null ? "bg-gray-700"
    : value >= 4 ? "bg-green-500"
    : value >= 2.5 ? "bg-amber-500"
    : "bg-red-500";
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="text-xs text-gray-400 w-24">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-300 w-8 text-right">
        {value != null ? value.toFixed(1) : "—"}
      </span>
    </div>
  );
}

export function FeedbackStatsPanel() {
  const [stats, setStats] = useState<DetailedStats | null>(null);

  useEffect(() => {
    fetchApi<DetailedStats>("/api/feedback/detailed-stats").then(setStats).catch(() => {});
  }, []);

  if (!stats) return null;

  const hasLow = stats.low_score_questions.length > 0;

  return (
    <div className="rounded-3xl border border-gray-800 bg-gray-900 p-5">
      <div className="text-white font-medium mb-4">回答满意度分析</div>
      <div className={`grid gap-6 ${hasLow ? "md:grid-cols-2" : ""}`}>
        <div>
          <div className="text-xs text-gray-500 mb-2">各维度平均分（1–5）</div>
          {Object.entries(DIM_LABELS).map(([key, label]) => (
            <ScoreBar key={key} label={label} value={stats.averages[key] ?? null} />
          ))}
        </div>

        {hasLow && (
          <div>
            <div className="text-xs text-gray-500 mb-2">低分问题（需改进）</div>
            <div className="space-y-2 max-h-48 overflow-auto pr-1">
              {stats.low_score_questions.map((q, i) => {
                const badDims = Object.entries(q.scores)
                  .filter(([, v]) => v != null && v <= 2)
                  .map(([k, v]) => `${DIM_LABELS[k] ?? k}:${v}★`)
                  .join("  ");
                return (
                  <div key={i} className="text-xs bg-gray-800 rounded-lg px-3 py-2">
                    <div className="text-gray-300 truncate" title={q.question}>{q.question}</div>
                    {badDims && <div className="text-red-400/70 mt-0.5">{badDims}</div>}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
