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
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <PromptTemplateList
        templates={prompts.templates}
        selectedId={prompts.selectedId}
        onSelect={prompts.selectTemplate}
      />
      <PromptDetailPanel
        detail={prompts.detail}
        selectedVersion={prompts.selectedVersion}
        draft={prompts.draft}
        setDraft={prompts.setDraft}
        variablesText={prompts.variablesText}
        setVariablesText={prompts.setVariablesText}
        rendered={prompts.rendered}
        saving={prompts.saving}
        testing={prompts.testing}
        error={prompts.error}
        onVersionChange={prompts.setSelectedVersion}
        onSave={prompts.saveTemplate}
        onTest={prompts.renderTemplate}
      />
    </div>
  );
}
