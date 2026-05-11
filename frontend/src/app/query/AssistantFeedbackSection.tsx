"use client";

import { useState } from "react";
import DetailedFeedbackPanel from "./DetailedFeedbackPanel";
import type { SourceSection } from "./types";

interface Props {
  question?: string;
  content: string;
  sources?: SourceSection[];
  strategy?: string;
  onLowScoreRetry?: (q: string) => void;
}

export function AssistantFeedbackSection({
  question,
  content,
  sources,
  strategy,
  onLowScoreRetry,
}: Props) {
  const [feedback, setFeedback] = useState<{
    rating: number;
    id: number | null;
    showDetail: boolean;
  } | null>(null);

  async function rate(r: number) {
    if (!question) return;
    const t = localStorage.getItem("token") ?? "";
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${t}`,
      },
      body: JSON.stringify({
        question,
        answer: content,
        sources: sources ?? [],
        rating: r,
        strategy: strategy ?? "parallel",
      }),
    });
    if (res.ok) {
      const d = await res.json();
      setFeedback({ rating: r, id: d.id ?? null, showDetail: true });
    }
  }

  if (!question) return null;

  return (
    <div className="mt-3 border-t border-gray-800 pt-2">
      {!feedback ? (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => rate(1)}
            className="text-lg transition-transform hover:scale-110"
          >
            👍
          </button>
          <button
            type="button"
            onClick={() => rate(-1)}
            className="text-lg transition-transform hover:scale-110"
          >
            👎
          </button>
          <span className="text-xs text-gray-700">对这个回答有帮助吗？</span>
        </div>
      ) : (
        <span className="text-xs text-gray-600">
          {feedback.rating === 1 ? "👍" : "👎"} 感谢反馈
        </span>
      )}
      {feedback?.showDetail && feedback.id !== null && (
        <DetailedFeedbackPanel
          feedbackId={feedback.id}
          onDone={(avg) => {
            setFeedback((s) => (s ? { ...s, showDetail: false } : null));
            if (avg < 2 && onLowScoreRetry) onLowScoreRetry(question);
          }}
          onSkip={() =>
            setFeedback((s) => (s ? { ...s, showDetail: false } : null))
          }
        />
      )}
    </div>
  );
}
