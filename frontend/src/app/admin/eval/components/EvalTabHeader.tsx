"use client";

import { BookOpenText, FileQuestion, FlaskConical, GitCompareArrows, SearchCheck } from "lucide-react";

import type { EvalTabKey } from "../types";

const TABS: Array<{
  key: EvalTabKey;
  label: string;
  description: string;
  icon: typeof BookOpenText;
}> = [
  {
    key: "dataset",
    label: "问答标准集",
    description: "有标准答案的问答评测",
    icon: BookOpenText,
  },
  {
    key: "objective",
    label: "客观题文档",
    description: "无答案题库自动抽题作答",
    icon: FileQuestion,
  },
  {
    key: "retrieval",
    label: "检索 Harness",
    description: "Recall / MRR / NDCG 量化",
    icon: SearchCheck,
  },
  {
    key: "faithfulness",
    label: "忠实度检测",
    description: "LLM 判断幻觉内容",
    icon: FlaskConical,
  },
  {
    key: "ab_test",
    label: "A/B 策略对比",
    description: "多策略横向指标对比",
    icon: GitCompareArrows,
  },
];

export function EvalTabHeader({
  activeTab,
  onTabChange,
}: {
  activeTab: EvalTabKey;
  onTabChange: (tab: EvalTabKey) => void;
}) {
  return (
    <div className="rounded-3xl border border-gray-800 bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.18),transparent_42%),radial-gradient(circle_at_top_right,rgba(14,165,233,0.12),transparent_36%),#111827] p-6">
      <div className="max-w-3xl">
        <h1 className="text-2xl font-semibold text-white">测试集评测</h1>
        <p className="mt-2 text-sm leading-6 text-gray-400">
          五类评测一体化：问答标准集、客观题、检索 Harness（Recall/MRR/NDCG）、
          忠实度幻觉检测、A/B 策略横向对比，全面量化系统效果。
        </p>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onTabChange(tab.key)}
              className={`group min-w-[210px] rounded-2xl border px-4 py-3 text-left transition-all ${
                active
                  ? "border-amber-400/60 bg-amber-400/10 shadow-[0_0_0_1px_rgba(251,191,36,0.22)]"
                  : "border-gray-800 bg-gray-900/70 hover:border-gray-700 hover:bg-gray-900"
              }`}
            >
              <div className="flex items-center gap-2">
                <Icon
                  size={15}
                  className={active ? "text-amber-300" : "text-gray-500 group-hover:text-gray-300"}
                />
                <span className={active ? "text-white" : "text-gray-300"}>{tab.label}</span>
              </div>
              <div className="mt-1 text-xs text-gray-500">{tab.description}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
