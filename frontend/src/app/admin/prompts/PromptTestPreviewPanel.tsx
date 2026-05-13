"use client";

import { PromptPreviewBlock } from "./PromptPreviewBlock";
import type { PromptDetail, PromptRender } from "./usePrompts";

type Props = {
  detail: PromptDetail;
  selectedVersion: string;
  draftSystem: string;
  draftUser: string;
  variablesText: string;
  rendered: PromptRender | null;
  saving: boolean;
  testing: boolean;
  error: string;
  onTest: () => void;
  onSave: () => void;
  onVariablesTextChange: (value: string) => void;
};

export function PromptTestPreviewPanel({
  detail,
  selectedVersion,
  draftSystem,
  draftUser,
  variablesText,
  rendered,
  saving,
  testing,
  error,
  onTest,
  onSave,
  onVariablesTextChange,
}: Props) {
  return (
    <>
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
            value={rendered?.system || draftSystem}
          />
          <PromptPreviewBlock
            label="User"
            value={rendered?.user || draftUser}
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
          onChange={(e) => onVariablesTextChange(e.target.value)}
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
    </>
  );
}
