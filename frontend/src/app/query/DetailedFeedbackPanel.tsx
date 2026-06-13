"use client";

import { useState } from "react";
import { fetchApi } from "@/lib/api";

const DIMENSIONS = [
  { key: "retrieval_score",    label: "检索准确度" },
  { key: "completeness_score", label: "答案完整性" },
  { key: "clarity_score",      label: "表述清晰度" },
  { key: "graph_score",        label: "图谱关联度" },
] as const;

type DimKey = typeof DIMENSIONS[number]["key"];

interface Props {
  feedbackId: number;
  onDone: (avgScore: number) => void;
  onSkip: () => void;
}

function StarRow({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-gray-400 w-24">{label}</span>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map(n => (
          <button key={n} type="button" onClick={() => onChange(n)}
            className={`w-5 h-5 text-sm transition-colors ${value >= n ? "text-amber-400" : "text-gray-700 hover:text-amber-500"}`}>
            ★
          </button>
        ))}
      </div>
    </div>
  );
}

export default function DetailedFeedbackPanel({ feedbackId, onDone, onSkip }: Props) {
  const [scores, setScores] = useState<Record<DimKey, number>>(
    { retrieval_score: 0, completeness_score: 0, clarity_score: 0, graph_score: 0 }
  );
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setSubmitting(true);
    try {
      await fetchApi("/api/feedback/detailed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query_id: feedbackId, ...scores, comment: comment || undefined }),
      });
      const filled = Object.values(scores).filter(v => v > 0);
      onDone(filled.length > 0 ? filled.reduce((a, b) => a + b, 0) / filled.length : 5);
    } catch {
      onSkip();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-3 pt-3 border-t border-gray-800">
      <div className="text-xs text-gray-500 mb-2">请对本次回答进行评分（可选）</div>
      <div className="divide-y divide-gray-800/50">
        {DIMENSIONS.map(dim => (
          <StarRow key={dim.key} label={dim.label} value={scores[dim.key]}
            onChange={n => setScores(s => ({ ...s, [dim.key]: n }))} />
        ))}
      </div>
      <textarea
        value={comment} onChange={e => setComment(e.target.value)}
        placeholder="补充意见（可选）..." rows={2}
        className="mt-2 w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 placeholder-gray-600 outline-none focus:border-gray-600 resize-none"
      />
      <div className="flex gap-2 mt-2">
        <button onClick={handleSubmit} disabled={submitting}
          className="px-4 py-1.5 bg-[#1B6BB5] text-white text-xs rounded-lg hover:bg-[#1558A0] disabled:opacity-50">
          {submitting ? "提交中…" : "提交"}
        </button>
        <button onClick={onSkip}
          className="px-4 py-1.5 bg-gray-800 text-gray-400 text-xs rounded-lg hover:text-white">
          跳过
        </button>
      </div>
    </div>
  );
}
