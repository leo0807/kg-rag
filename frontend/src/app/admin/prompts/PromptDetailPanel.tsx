"use client";

import { PromptDetailContent } from "./PromptDetailContent";
import type {
  PromptComparison,
  PromptDetail,
  PromptDraft,
  PromptRender,
} from "./usePrompts";

type Props = {
  detail: PromptDetail | null;
  templatesCount: number;
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
  onRetry: () => void;
};

export function PromptDetailPanel(props: Props) {
  if (!props.detail) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-950 p-6 text-slate-300">
        <div className="space-y-3">
          <p>请选择一个 Prompt 模板。</p>
          {props.templatesCount === 0 && (
            <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              模板列表加载失败或为空，请点击“重新加载”重试。
            </div>
          )}
          <button
            type="button"
            onClick={props.onRetry}
            className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 hover:border-slate-500"
          >
            重新加载
          </button>
        </div>
      </section>
    );
  }
  return <PromptDetailContent {...props} detail={props.detail} />;
}
