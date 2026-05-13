"use client";

import { PromptField } from "./PromptField";
import { PromptTestPreviewPanel } from "./PromptTestPreviewPanel";
import { PromptVersionComparePanel } from "./PromptVersionComparePanel";
import type {
  PromptComparison,
  PromptDetail,
  PromptDraft,
  PromptRender,
} from "./usePrompts";

type Props = {
  detail: PromptDetail;
  selectedVersion: string;
  draft: PromptDraft;
  setDraft: React.Dispatch<React.SetStateAction<PromptDraft>>;
  variablesText: string;
  setVariablesText: React.Dispatch<React.SetStateAction<string>>;
  rendered: PromptRender | null;
  comparison: PromptComparison | null;
  compareVersion: string;
  setCompareVersion: (version: string) => void;
  saving: boolean;
  testing: boolean;
  comparing: boolean;
  error: string;
  onVersionChange: (version: string) => void;
  onSave: () => void;
  onTest: () => void;
  onCompare: () => void;
};

export function PromptDetailContent({
  detail,
  selectedVersion,
  draft,
  setDraft,
  variablesText,
  setVariablesText,
  rendered,
  comparison,
  compareVersion,
  setCompareVersion,
  saving,
  testing,
  comparing,
  error,
  onVersionChange,
  onSave,
  onTest,
  onCompare,
}: Props) {
  return (
    <section className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">{detail.id}</h1>
          <p className="text-sm text-slate-400">{detail.description}</p>
          <p className="mt-1 text-xs text-slate-500">
            文件：{detail.file || "内置模板"}
          </p>
        </div>
        <div className="min-w-[220px]">
          <label
            htmlFor="prompt-version"
            className="mb-1 block text-xs text-slate-400"
          >
            版本
          </label>
          <select
            id="prompt-version"
            value={selectedVersion}
            onChange={(e) => onVersionChange(e.target.value)}
            className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
          >
            {detail.versions.map((version) => (
              <option key={version.name} value={version.name}>
                {version.name} · weight {version.weight}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <PromptField label="模型">
          <input
            value={draft.model_preference}
            onChange={(e) =>
              setDraft((prev) => ({
                ...prev,
                model_preference: e.target.value,
              }))
            }
            className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          />
        </PromptField>
        <PromptField label="Max Tokens">
          <input
            type="number"
            value={draft.max_tokens}
            onChange={(e) =>
              setDraft((prev) => ({
                ...prev,
                max_tokens: Number(e.target.value) || 0,
              }))
            }
            className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          />
        </PromptField>
        <PromptField label="Temperature">
          <input
            type="number"
            step="0.1"
            value={draft.temperature}
            onChange={(e) =>
              setDraft((prev) => ({
                ...prev,
                temperature: Number(e.target.value) || 0,
              }))
            }
            className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          />
        </PromptField>
        <PromptField label="Weight">
          <input
            type="number"
            value={draft.weight}
            onChange={(e) =>
              setDraft((prev) => ({
                ...prev,
                weight: Number(e.target.value) || 0,
              }))
            }
            className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
          />
        </PromptField>
      </div>

      <PromptField label="描述 / 变量">
        <input
          value={draft.description}
          onChange={(e) =>
            setDraft((prev) => ({ ...prev, description: e.target.value }))
          }
          className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
        />
      </PromptField>
      <PromptField label="变量名（逗号分隔）">
        <input
          value={draft.variables}
          onChange={(e) =>
            setDraft((prev) => ({ ...prev, variables: e.target.value }))
          }
          className="w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
        />
      </PromptField>

      <div className="grid gap-4 lg:grid-cols-2">
        <PromptField label="System Prompt">
          <textarea
            value={draft.system}
            onChange={(e) =>
              setDraft((prev) => ({ ...prev, system: e.target.value }))
            }
            rows={14}
            className="min-h-[280px] w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm leading-6"
          />
        </PromptField>
        <PromptField label="User Prompt">
          <textarea
            value={draft.user}
            onChange={(e) =>
              setDraft((prev) => ({ ...prev, user: e.target.value }))
            }
            rows={14}
            className="min-h-[280px] w-full rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm leading-6"
          />
        </PromptField>
      </div>
      <PromptTestPreviewPanel
        detail={detail}
        selectedVersion={selectedVersion}
        draftSystem={draft.system}
        draftUser={draft.user}
        variablesText={variablesText}
        rendered={rendered}
        saving={saving}
        testing={testing}
        error={error}
        onTest={onTest}
        onSave={onSave}
        onVariablesTextChange={setVariablesText}
      />

      <PromptVersionComparePanel
        detail={detail}
        selectedVersion={selectedVersion}
        compareVersion={compareVersion}
        setCompareVersion={setCompareVersion}
        comparison={comparison}
        comparing={comparing}
        onCompare={onCompare}
      />
    </section>
  );
}
