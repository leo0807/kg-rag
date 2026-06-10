"use client";

import { Lightbulb, X } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

interface Props {
  conversationId: string;
  onSelect: (q: string) => void;
  triggerKey?: number; // increment to trigger new fetch
}

export function QuestionSuggestions({ conversationId, onSelect, triggerKey }: Props) {
  const [questions, setQuestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!conversationId || triggerKey === undefined) return;
    setDismissed(false);
    setLoading(true);
    setQuestions([]);
    fetchApi<{ questions: string[] }>("/api/recommend/questions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId }),
    })
      .then((d) => setQuestions(d.questions))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [conversationId, triggerKey]);

  if (dismissed || (!loading && questions.length === 0)) return null;

  return (
    <div className="mx-4 mb-3 rounded-xl border border-indigo-900/40 bg-indigo-950/30 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-xs text-indigo-400">
          <Lightbulb size={12} />
          <span>您可能还想问：</span>
        </div>
        <button onClick={() => setDismissed(true)}
          className="text-gray-600 hover:text-gray-400 transition-colors">
          <X size={12} />
        </button>
      </div>

      {loading ? (
        <div className="flex gap-1.5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-6 w-24 rounded-full bg-gray-800 animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {questions.map((q, i) => (
            <button key={i} type="button"
              onClick={() => { onSelect(q); setDismissed(true); }}
              className="px-3 py-1 text-xs text-indigo-300 bg-indigo-900/30 border border-indigo-800/60
                         rounded-full hover:bg-indigo-800/40 hover:border-indigo-700 transition-colors
                         text-left max-w-[220px] truncate">
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
