"use client";
import { Download } from "lucide-react";
import type { Strategy } from "./types";

const strategies: { value: Strategy; label: string; desc: string }[] = [
  { value: "parallel", label: "并行检索", desc: "同时检索，RRF 融合" },
  { value: "sequential", label: "串行检索", desc: "图谱优先，精确查询" },
  { value: "graph_augmented", label: "图谱增强", desc: "向量召回+图谱扩展" },
  { value: "multi_hop", label: "多跳推理", desc: "复杂因果分析" },
  { value: "agent", label: "Agent", desc: "工具调用式多步推理" },
];

interface Props {
  query: string;
  strategy: Strategy;
  loading: boolean;
  streaming: boolean;
  hasResult: boolean;
  historyLen: number;
  onQuery: (q: string) => void;
  onStrategy: (s: Strategy) => void;
  onSubmit: () => void;
  onExport: () => void;
}

export default function QueryInput({
  query,
  strategy,
  loading,
  streaming,
  hasResult,
  historyLen,
  onQuery,
  onStrategy,
  onSubmit,
  onExport,
}: Props) {
  return (
    <>
      <textarea
        value={query}
        onChange={(e) => onQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onSubmit();
        }}
        placeholder="输入问题，例如：液压导管修理需要哪些工具？"
        className="w-full h-24 px-4 py-3 bg-gray-900 border border-gray-700
                   rounded-xl text-gray-200 text-sm resize-none outline-none
                   focus:border-indigo-500 placeholder-gray-600 transition-colors"
      />

      <div className="flex gap-2 mt-3 mb-4 flex-wrap">
        {strategies.map((s) => (
          <button
            type="button"
            key={s.value}
            onClick={() => onStrategy(s.value)}
            title={s.desc}
            className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
              strategy === s.value
                ? "bg-indigo-600 border-indigo-600 text-white"
                : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-3 mb-8">
        <button
          type="button"
          onClick={onSubmit}
          disabled={!query.trim() || loading || streaming}
          className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg
                     disabled:opacity-40 hover:bg-indigo-500 transition-colors"
        >
          {loading ? "检索中..." : streaming ? "生成中..." : "提交问题"}
        </button>
        <span className="text-xs text-gray-600">⌘ + Enter 快捷提交</span>
        {historyLen > 0 && (
          <span className="text-xs text-indigo-400/70">
            第 {historyLen / 2 + 1} 轮对话
          </span>
        )}
        <button
          type="button"
          onClick={onExport}
          disabled={!hasResult || streaming}
          className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1
                     bg-gray-800 text-gray-400 text-xs rounded hover:text-white
                     hover:bg-gray-700 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Download size={12} /> 导出 MD
        </button>
      </div>
    </>
  );
}
