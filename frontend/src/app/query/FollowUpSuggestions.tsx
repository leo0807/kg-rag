"use client";

interface Props {
  questions: string[];
  sourceDocIds?: string[];
  onFollowUp?: (q: string, sourceDocIds?: string[]) => void;
}

export function FollowUpSuggestions({
  questions,
  sourceDocIds,
  onFollowUp,
}: Props) {
  if (questions.length === 0) return null;
  return (
    <div className="mt-3 pt-3 border-t border-gray-800 animate-fade-in">
      <div className="text-xs text-gray-600 mb-2">追问建议</div>
      <div className="flex flex-col gap-1.5">
        {questions.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => onFollowUp?.(q, sourceDocIds)}
            className="text-left px-3 py-1.5 text-xs text-indigo-300/80 bg-indigo-950/30
                       border border-indigo-800/40 rounded-lg hover:border-indigo-500/60
                       hover:text-indigo-200 hover:bg-indigo-950/50 transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
