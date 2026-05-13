"use client";

import { PromptPreviewBlock } from "./PromptPreviewBlock";
import { PromptVersionBadges } from "./PromptVersionBadges";
import type { PromptDetail, PromptRender } from "./usePrompts";

type Props = {
  detail: PromptDetail;
  selectedVersion: string;
  compareVersion: string;
  setCompareVersion: (value: string) => void;
  comparison: { left: PromptRender; right: PromptRender } | null;
  comparing: boolean;
  onCompare: () => void;
};

export function PromptVersionComparePanel({
  detail,
  selectedVersion,
  compareVersion,
  setCompareVersion,
  comparison,
  comparing,
  onCompare,
}: Props) {
  return (
    <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">版本对比</h3>
          <p className="text-xs text-slate-500">
            用同一组变量渲染两个版本，快速看差异。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={compareVersion}
            onChange={(e) => setCompareVersion(e.target.value)}
            className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          >
            {detail.versions.map((version) => (
              <option key={version.name} value={version.name}>
                {version.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={onCompare}
            disabled={
              comparing || !compareVersion || compareVersion === selectedVersion
            }
            className="rounded-xl border border-fuchsia-500/50 bg-fuchsia-500/10 px-4 py-2 text-sm font-medium text-fuchsia-200 disabled:opacity-50"
          >
            {comparing ? "对比中..." : "一键对比"}
          </button>
        </div>
      </div>
      <PromptVersionBadges
        versions={detail.versions}
        selectedVersion={selectedVersion}
      />
      {comparison && (
        <div className="grid gap-4 lg:grid-cols-2">
          <PromptPreviewBlock
            label={`当前版本 ${comparison.left.version}`}
            value={comparison.left.system}
          />
          <PromptPreviewBlock
            label={`对比版本 ${comparison.right.version}`}
            value={comparison.right.system}
          />
          <PromptPreviewBlock
            label={`当前版本 ${comparison.left.version} / User`}
            value={comparison.left.user}
          />
          <PromptPreviewBlock
            label={`对比版本 ${comparison.right.version} / User`}
            value={comparison.right.user}
          />
        </div>
      )}
    </div>
  );
}
