"use client";

import { X } from "lucide-react";

interface Props { onClose: () => void }

export function GNNHelpPanel({ onClose }: Props) {
  return (
    <div className="bg-violet-950/30 border border-violet-800/40 rounded-xl p-5 relative">
      <button onClick={onClose}
        className="absolute top-3 right-3 text-gray-500 hover:text-white transition-colors">
        <X size={14} />
      </button>
      <h3 className="text-sm font-semibold text-violet-300 mb-2">这个页面是做什么的？</h3>
      <p className="text-sm text-gray-300 leading-relaxed mb-3">
        这是一个"让系统变得更聪明"的训练页面。系统在回答问题时，不仅会查找关键词，
        还会理解文档章节之间的关联关系——例如「前处理」和「后处理」章节通常相邻出现。
        GNN（图神经网络）训练就是让系统学习这些结构规律。
      </p>
      <div className="space-y-1.5 text-sm text-gray-400">
        {[
          "首次使用前点击「开始训练」，训练一次即可（大约 5–20 分钟）。",
          "训练结束后无需任何操作，系统会自动使用新模型。",
          "当文档库有大量新增或删除时，建议重新训练一次以保持准确性。",
        ].map((text, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="text-violet-400 shrink-0 mt-0.5">{["①","②","③"][i]}</span>
            <span>{text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
