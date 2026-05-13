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

export function PromptDetailPanel(props: Props) {
  if (!props.detail) {
    return (
      <section className="rounded-xl border border-slate-800 bg-slate-950 p-6 text-slate-300">
        请选择一个 Prompt 模板。
      </section>
    );
  }
  return <PromptDetailContent {...props} detail={props.detail} />;
}
