"use client";

import { RotateCcw, Zap } from "lucide-react";
import { Strategy } from "./types";

const STRATEGIES: { value: Strategy; label: string; title: string }[] = [
    { value: "parallel",        label: "并行",   title: "全文 + 向量 RRF 融合" },
    { value: "sequential",      label: "串行",   title: "全文优先，精确查询" },
    { value: "graph_augmented", label: "图谱",   title: "向量召回 + 图谱扩展" },
    { value: "multi_hop",       label: "多跳",   title: "多跳推理，复杂因果" },
    { value: "counterfactual",  label: "反事实", title: "假设推理：去掉 X 后还能满足 Y 吗？" },
];

interface Props {
    strategy: Strategy;
    useHyde: boolean;
    historyLen: number;
    onStrategy: (s: Strategy) => void;
    onHydeToggle: (v: boolean) => void;
    onClear: () => void;
}

export function StrategySelector({ strategy, useHyde, historyLen, onStrategy, onHydeToggle, onClear }: Props) {
    return (
        <div className="flex items-center gap-2 mb-3">
            <div className="flex gap-1 bg-gray-900 border border-gray-800 rounded-lg p-0.5">
                {STRATEGIES.map(s => (
                    <button key={s.value} onClick={() => onStrategy(s.value)} title={s.title}
                        className={`px-2.5 py-1 rounded text-xs transition-colors ${strategy === s.value
                            ? s.value === "counterfactual" ? "bg-amber-600 text-white" : "bg-indigo-600 text-white"
                            : "text-gray-500 hover:text-gray-300"
                        }`}>
                        {s.label}
                    </button>
                ))}
            </div>

            <button
                onClick={() => onHydeToggle(!useHyde)}
                title="启用后系统先生成假设答案再检索，适合复杂技术问题，响应稍慢"
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs transition-colors ${
                    useHyde
                        ? "bg-violet-600 border-violet-500 text-white"
                        : "bg-gray-900 border-gray-800 text-gray-500 hover:text-gray-300"
                }`}
            >
                <Zap size={11} className={useHyde ? "text-violet-200" : ""} />
                增强
            </button>

            {historyLen > 0 && (
                <span className="text-xs text-gray-600 ml-1">{Math.floor(historyLen / 2)} 轮对话</span>
            )}
            {historyLen > 0 && (
                <button onClick={onClear}
                    className="ml-auto flex items-center gap-1 text-xs text-gray-600 hover:text-gray-400 transition-colors">
                    <RotateCcw size={11} />清空对话
                </button>
            )}
        </div>
    );
}
