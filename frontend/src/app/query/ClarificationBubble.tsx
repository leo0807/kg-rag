"use client";

interface Props {
  message: string;
  options: string[];
  onSelect: (option: string) => void;
}

export function ClarificationBubble({ message, options, onSelect }: Props) {
  return (
    <div className="max-w-md rounded-lg border border-amber-700/40 bg-[var(--bg-secondary)] p-4 shadow-lg">
      <p className="mb-3 text-sm text-[var(--text-secondary)]">🤔 {message}</p>
      <div className="flex flex-col gap-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onSelect(option)}
            className="rounded-md border border-[var(--border-default)] bg-[var(--bg-card)] px-3 py-2 text-left text-sm text-[var(--text-primary)] transition-colors hover:border-[var(--color-primary)] hover:bg-[var(--color-primary-light)]"
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}
