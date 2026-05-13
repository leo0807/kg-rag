"use client";

import { PromptField } from "./PromptField";
import { PromptPreviewBlock } from "./PromptPreviewBlock";
import { PromptVersionBadges } from "./PromptVersionBadges";
import type { PromptDetail, PromptDraft, PromptRender } from "./usePrompts";

type Props = {
  detail: PromptDetail | null;
  selectedVersion: string;
  draft: PromptDraft;
  setDraft: React.Dispatch<React.SetStateAction<PromptDraft>>;
  variablesText: string;
  setVariablesText: React.Dispatch<React.SetStateAction<string>>;
  rendered: PromptRender | null;
  saving: boolean;
  testing: boolean;
  error: string;
  onVersionChange: (version: string) => void;
  onSave: () => void;
  onTest: () => void;
};

export function PromptDetailPanel({
  detail,
  selectedVersion,
  draft,
  setDraft,
  variablesText,
  setVariablesText,
  rendered,
  saving,
  testing,
  error,
  onVersionChange,
  onSave,
  onTest,
}: Props) {
  if (!detail) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-950 p-6 text-slate-300">
        请选择一个 Prompt 模板。
      </section>
    );
  }

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
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onTest}
          disabled={testing}
          className="rounded-xl border border-sky-500/50 bg-sky-500/10 px-4 py-2 text-sm font-medium text-sky-200 disabled:opacity-50"
        >
          {testing ? "测试中..." : "一键测试"}
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="rounded-xl border border-emerald-500/50 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-200 disabled:opacity-50"
        >
          {saving ? "保存中..." : "保存模板"}
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-100">模板预览</h3>
          <span className="text-xs text-slate-500">
            当前版本：{selectedVersion || detail.selected_version}
          </span>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <PromptPreviewBlock
            label="System"
            value={rendered?.system || draft.system}
          />
          <PromptPreviewBlock
            label="User"
            value={rendered?.user || draft.user}
          />
        </div>
      </div>

      <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-100">一键测试输入</h3>
          <span className="text-xs text-slate-500">
            POST /api/admin/prompts/{detail.id}/render
          </span>
        </div>
        <textarea
          value={variablesText}
          onChange={(e) => setVariablesText(e.target.value)}
          rows={8}
          className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm leading-6 text-slate-100"
        />
        {rendered && (
          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs text-slate-300">
            <div>模型：{rendered.model || "默认"}</div>
            <div>max_tokens：{rendered.max_tokens}</div>
            <div>temperature：{rendered.temperature}</div>
            <div className="mt-3 text-slate-500">
              返回消息数：{rendered.messages.length}
            </div>
          </div>
        )}
      </div>

      <PromptVersionBadges
        versions={detail.versions}
        selectedVersion={selectedVersion}
      />
    </section>
  );
}
