"use client";

import { useState } from "react";
import type { QueryMetrics } from "./types";

interface Props {
  metrics?: QueryMetrics;
}

export function MetricsPanel({ metrics }: Props) {
  const [open, setOpen] = useState(false);
  if (!metrics || metrics.total_ms === 0) return null;

  const totalMs = metrics.total_ms;
  const stages = Object.entries(metrics.stages ?? {}).sort((a, b) => b[1] - a[1]);
  const totalTokens = metrics.tokens?.total ?? 0;
  const costUsd = metrics.cost_usd ?? 0;

  function fmtMs(ms: number) {
    return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
  }

  // top bottleneck stage
  const bottleneck = stages[0];
  const bottleneckPct = bottleneck ? Math.round((bottleneck[1] / totalMs) * 100) : 0;

  return (
    <div className="mt-2 border-t border-gray-800 pt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-xs text-gray-600 hover:text-gray-400 transition-colors"
      >
        <span>⏱ {fmtMs(totalMs)}</span>
        {costUsd > 0 && <span>💰 ${costUsd.toFixed(4)}</span>}
        {totalTokens > 0 && <span>🔤 {totalTokens.toLocaleString()}</span>}
        <span className="ml-1">{open ? "▲" : "▼"} 详情</span>
      </button>

      {open && (
        <div className="mt-2 rounded-lg border border-gray-800 bg-gray-950 p-3">
          <div className="text-xs font-medium text-gray-400 mb-2">查询性能详情</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-600">
                <th className="text-left pb-1">阶段</th>
                <th className="text-right pb-1 pr-3">耗时</th>
                <th className="text-left pb-1">占比</th>
              </tr>
            </thead>
            <tbody>
              {stages.map(([stage, ms]) => {
                const pct = Math.round((ms / totalMs) * 100);
                const bars = Math.round(pct / 5);
                return (
                  <tr key={stage} className="border-t border-gray-800/50">
                    <td className="py-1 text-gray-300">{stage}</td>
                    <td className="py-1 text-right pr-3 text-gray-400 font-mono">{fmtMs(ms)}</td>
                    <td className="py-1 text-gray-500">
                      {"█".repeat(bars)}{"░".repeat(Math.max(0, 20 - bars))} {pct}%
                    </td>
                  </tr>
                );
              })}
              <tr className="border-t border-gray-700 font-medium">
                <td className="pt-1 text-gray-300">总计</td>
                <td className="pt-1 text-right pr-3 text-gray-300 font-mono">{fmtMs(totalMs)}</td>
                <td />
              </tr>
            </tbody>
          </table>
          {(totalTokens > 0 || metrics.candidates_retrieved > 0) && (
            <div className="mt-2 pt-2 border-t border-gray-800 grid grid-cols-3 gap-2 text-xs text-gray-500">
              {totalTokens > 0 && <span>Token: {totalTokens.toLocaleString()}</span>}
              {metrics.candidates_retrieved > 0 && <span>召回: {metrics.candidates_retrieved}</span>}
              {metrics.candidates_after_rerank > 0 && <span>保留: {metrics.candidates_after_rerank}</span>}
            </div>
          )}
          {bottleneck && bottleneckPct >= 50 && (
            <div className="mt-2 text-[10px] text-yellow-600">
              ⚠️ {bottleneck[0]}占用 {bottleneckPct}% 时间，是当前瓶颈
            </div>
          )}
        </div>
      )}
    </div>
  );
}
