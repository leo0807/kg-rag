"use client";

import { StrategyStats } from "./types";
import { StrategyBadge } from "./components";

interface Props {
    loading:       boolean;
    strategyStats: StrategyStats | null;
}

export function StrategyTab({ loading, strategyStats }: Props) {
    if (loading || !strategyStats) return null;

    return (
        <div className="space-y-4">
            <p className="text-xs text-gray-500">
                数据来源：LLMUsage（延迟 / Token）+ QueryFeedback（好评率 / 来源数）·
                仅统计有明确 👍/👎 评分的记录计算好评率
            </p>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="bg-gray-900 sticky top-0 z-10">
                        <tr>
                            <th className="px-3 py-2.5 text-xs font-medium text-gray-400 text-left whitespace-nowrap">策略</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-gray-400 text-right whitespace-nowrap">调用次数</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-gray-400 text-right whitespace-nowrap">平均延迟(ms)</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-gray-400 text-right whitespace-nowrap">平均 Token</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-gray-400 text-right whitespace-nowrap">总 Token</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-gray-400 text-right whitespace-nowrap">均费用($)</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-gray-400 text-right whitespace-nowrap">👍 好评率</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-gray-400 text-right whitespace-nowrap">有效评分数</th>
                            <th className="px-3 py-2.5 text-xs font-medium text-gray-400 text-right whitespace-nowrap">均来源数</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                        {strategyStats.strategies.map(row => {
                            const rate = row.positive_rate;
                            const rateColor =
                                rate === null       ? "text-gray-600"   :
                                rate >= 0.8         ? "text-emerald-400" :
                                rate >= 0.6         ? "text-amber-400"   :
                                                      "text-red-400";
                            return (
                                <tr key={row.strategy} className="hover:bg-gray-900/50 transition-colors">
                                    <td className="px-3 py-3">
                                        <StrategyBadge strategy={row.strategy} />
                                    </td>
                                    <td className="px-3 py-3 text-right font-semibold text-white">
                                        {row.call_count.toLocaleString()}
                                    </td>
                                    <td className="px-3 py-3 text-right text-gray-300 font-mono">
                                        {row.avg_latency_ms != null ? row.avg_latency_ms.toLocaleString() : "—"}
                                    </td>
                                    <td className="px-3 py-3 text-right text-gray-300 font-mono">
                                        {row.avg_tokens != null ? row.avg_tokens.toLocaleString() : "—"}
                                    </td>
                                    <td className="px-3 py-3 text-right text-gray-500 font-mono text-xs">
                                        {row.total_tokens.toLocaleString()}
                                    </td>
                                    <td className="px-3 py-3 text-right text-gray-500 font-mono text-xs">
                                        {row.avg_cost_usd != null ? row.avg_cost_usd.toFixed(5) : "—"}
                                    </td>
                                    <td className={`px-3 py-3 text-right font-semibold ${rateColor}`}>
                                        {rate != null ? (
                                            <span className="flex items-center justify-end gap-1.5">
                                                <span
                                                    className="inline-block h-1.5 rounded-full bg-current opacity-60"
                                                    style={{ width: `${Math.round(rate * 48)}px` }}
                                                />
                                                {(rate * 100).toFixed(1)}%
                                            </span>
                                        ) : "—"}
                                    </td>
                                    <td className="px-3 py-3 text-right text-gray-500 text-xs">
                                        {row.explicit_ratings > 0
                                            ? `👍${row.positive_count} 👎${row.negative_count}`
                                            : "—"}
                                    </td>
                                    <td className="px-3 py-3 text-right text-gray-300">
                                        {row.avg_source_count != null ? row.avg_source_count : "—"}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
                {strategyStats.strategies.length === 0 && (
                    <div className="text-center py-12 text-gray-600 text-sm">
                        暂无数据 — 请先产生查询记录和用户反馈
                    </div>
                )}
            </div>
            {/* 路由建议 */}
            {strategyStats.strategies.length > 0 && (() => {
                const best = [...strategyStats.strategies]
                    .filter(r => r.positive_rate != null && r.explicit_ratings >= 3)
                    .sort((a, b) => (b.positive_rate ?? 0) - (a.positive_rate ?? 0))[0];
                const fastest = [...strategyStats.strategies]
                    .filter(r => r.avg_latency_ms != null)
                    .sort((a, b) => (a.avg_latency_ms ?? 0) - (b.avg_latency_ms ?? 0))[0];
                if (!best && !fastest) return null;
                return (
                    <div className="mt-4 p-4 bg-gray-900 border border-gray-800 rounded-xl space-y-2">
                        <div className="text-xs font-medium text-gray-400 mb-2">自动路由建议</div>
                        {best && (
                            <div className="flex items-center gap-2 text-xs text-gray-300">
                                <span className="text-emerald-400 font-semibold">最高好评率</span>
                                <StrategyBadge strategy={best.strategy} />
                                <span className="text-gray-500">
                                    {((best.positive_rate ?? 0) * 100).toFixed(1)}%
                                    （{best.explicit_ratings} 条有效评分）
                                    — 建议作为复杂问题的默认策略
                                </span>
                            </div>
                        )}
                        {fastest && (
                            <div className="flex items-center gap-2 text-xs text-gray-300">
                                <span className="text-indigo-400 font-semibold">最低延迟</span>
                                <StrategyBadge strategy={fastest.strategy} />
                                <span className="text-gray-500">
                                    均 {fastest.avg_latency_ms?.toLocaleString()}ms
                                    — 建议作为简单查询的快速路径
                                </span>
                            </div>
                        )}
                    </div>
                );
            })()}
        </div>
    );
}
