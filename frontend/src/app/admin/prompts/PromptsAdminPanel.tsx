"use client";

import { PromptDetailPanel } from "./PromptDetailPanel";
import { PromptTemplateList } from "./PromptTemplateList";
import { usePrompts } from "./usePrompts";

export function PromptsAdminPanel() {
  const prompts = usePrompts();

  if (prompts.loading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 text-slate-300">
        正在加载 Prompt 模板...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {prompts.error && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          <span>{prompts.error}</span>
          <button
            type="button"
            onClick={prompts.retryLoad}
            className="rounded-xl border border-amber-400/50 bg-amber-400/10 px-3 py-1.5 text-xs font-medium text-amber-100 hover:bg-amber-400/20"
          >
            重新加载
          </button>
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <PromptTemplateList
          templates={prompts.templates}
          selectedId={prompts.selectedId}
          onSelect={prompts.selectTemplate}
        />
        <PromptDetailPanel
          detail={prompts.detail}
          templatesCount={prompts.templates.length}
          selectedVersion={prompts.selectedVersion}
          draft={prompts.draft}
          setDraft={prompts.setDraft}
          variablesText={prompts.variablesText}
          setVariablesText={prompts.setVariablesText}
          rendered={prompts.rendered}
          comparison={prompts.comparison}
          compareVersion={prompts.compareVersion}
          setCompareVersion={prompts.setCompareVersion}
          saving={prompts.saving}
          testing={prompts.testing}
          comparing={prompts.comparing}
          error={prompts.error}
          onVersionChange={prompts.setSelectedVersion}
          onSave={prompts.saveTemplate}
          onTest={prompts.renderTemplate}
          onCompare={prompts.compareTemplate}
          onRetry={prompts.retryLoad}
        />
      </div>
    </div>
  );
}
