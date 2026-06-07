"use client";

import { useState } from "react";
import { FeedbackButtons } from "./FeedbackButtons";
import { FeedbackPanel } from "./FeedbackPanel";
import DetailedFeedbackPanel from "./DetailedFeedbackPanel";
import type { SourceSection } from "./types";

interface Props {
  question?: string;
  content: string;
  sources?: SourceSection[];
  strategy?: string;
  onLowScoreRetry?: (q: string) => void;
}

type Mode = "idle" | "annotate" | "rated";

export function AssistantFeedbackSection({
  question,
  content,
  sources,
  strategy,
  onLowScoreRetry,
}: Props) {
  const [mode, setMode]       = useState<Mode>("idle");
  const [rating, setRating]   = useState<number | null>(null);
  const [feedbackId, setFeedbackId] = useState<number | null>(null);
  const [showDetail, setShowDetail] = useState(false);

  if (!question) return null;

  async function submitRating(r: number) {
    const token = localStorage.getItem("token") ?? "";
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        question,
        answer:   content,
        sources:  sources ?? [],
        rating:   r,
        strategy: strategy ?? "parallel",
      }),
    });
    if (res.ok) {
      const d = await res.json();
      setRating(r);
      setFeedbackId(d.id ?? null);
      setMode("rated");
      setShowDetail(true);
    }
  }

  // 📝 标注模式：展开 FeedbackPanel
  if (mode === "annotate") {
    return (
      <div className="mt-3 border-t border-gray-800 pt-2">
        <FeedbackPanel
          question={question}
          answer={content}
          sources={sources}
          strategy={strategy}
          onClose={() => setMode("idle")}
          onSubmitted={id => { setFeedbackId(id); setMode("rated"); }}
        />
      </div>
    );
  }

  // 评分后：显示感谢 + 可选详细评分
  if (mode === "rated") {
    return (
      <div className="mt-3 border-t border-gray-800 pt-2">
        <span className="text-xs text-gray-600">
          {rating === 1 ? "👍" : rating === -1 ? "👎" : "📝"} 感谢反馈
        </span>
        {showDetail && feedbackId !== null && rating !== null && (
          <DetailedFeedbackPanel
            feedbackId={feedbackId}
            onDone={(avg) => {
              setShowDetail(false);
              if (avg < 2 && onLowScoreRetry) onLowScoreRetry(question);
            }}
            onSkip={() => setShowDetail(false)}
          />
        )}
      </div>
    );
  }

  // 默认：三个按钮
  return (
    <div className="mt-3 border-t border-gray-800 pt-2">
      <FeedbackButtons
        onThumbsUp={() => submitRating(1)}
        onThumbsDown={() => submitRating(-1)}
        onAnnotate={() => setMode("annotate")}
      />
    </div>
  );
}
