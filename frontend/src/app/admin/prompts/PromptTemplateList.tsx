"use client";

import type { PromptSummary } from "./usePrompts";

type Props = {
  templates: PromptSummary[];
  selectedId: string;
  onSelect: (id: string, version: string) => void;
};

export function PromptTemplateList({ templates, selectedId, onSelect }: Props) {
  return (
    <aside className="rounded-2xl border border-slate-800 bg-slate-950 p-4">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-100">Prompt 模板</h2>
        <p className="text-sm text-slate-400">共 {templates.length} 个模板</p>
      </div>
      <div className="space-y-2">
        {templates.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id, item.active_version)}
            className={`w-full rounded-xl border px-3 py-3 text-left transition-colors ${
              selectedId === item.id
                ? "border-indigo-500 bg-indigo-500/10 text-slate-50"
                : "border-slate-800 bg-slate-900 text-slate-200 hover:border-slate-600"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{item.id}</span>
              <span className="text-xs text-slate-400">
                {item.active_version}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-400">{item.description}</p>
            <p className="mt-2 text-[11px] text-slate-500">
              {item.versions.length} 个版本
            </p>
          </button>
        ))}
      </div>
    </aside>
  );
}
