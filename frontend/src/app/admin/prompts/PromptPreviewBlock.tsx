"use client";

type Props = {
  label: string;
  value: string;
};

export function PromptPreviewBlock({ label, value }: Props) {
  return (
    <div>
      <div className="mb-2 text-xs text-slate-500">{label}</div>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs leading-6 text-slate-200">
        {value}
      </pre>
    </div>
  );
}
