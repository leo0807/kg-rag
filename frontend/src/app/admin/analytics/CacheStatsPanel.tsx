"use client";

import { BarChart2, MessageSquare, TrendingUp, Zap } from "lucide-react";
import type { CacheHitStats } from "./types";
import { SummaryCard } from "./components";

interface Props { stats: CacheHitStats }

export function CacheStatsPanel({ stats }: Props) {
  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-xl px-5 py-4 flex flex-wrap gap-6 text-sm">
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wider block mb-0.5">状态</span>
          <span className={stats.store.config.enabled ? "text-emerald-400" : "text-red-400"}>
            {stats.store.config.enabled ? "已启用" : "已禁用"}
          </span>
        </div>
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wider block mb-0.5">相似度阈值</span>
          <span className="text-white font-mono">{stats.store.config.threshold}</span>
        </div>
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wider block mb-0.5">TTL</span>
          <span className="text-white font-mono">{stats.store.config.ttl / 3600}h</span>
        </div>
        <div>
          <span className="text-gray-500 text-xs uppercase tracking-wider block mb-0.5">活跃条目</span>
          <span className="text-white font-mono">{stats.store.active_entries}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard icon={Zap}           label="缓存命中次数" value={stats.hits.hit_count} />
        <SummaryCard icon={BarChart2}     label="节省 Token 数" value={stats.hits.tokens_saved.toLocaleString()} />
        <SummaryCard icon={TrendingUp}    label="节省费用 (¥)" value={`¥${stats.hits.cost_saved_cny.toFixed(4)}`} />
        <SummaryCard icon={MessageSquare} label="平均相似度"   value={stats.hits.avg_similarity ? stats.hits.avg_similarity.toFixed(4) : "—"} />
      </div>

      {stats.by_strategy.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wider">按策略分布</div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-left">
                <th className="px-5 py-2.5">策略</th>
                <th className="px-5 py-2.5">命中次数</th>
                <th className="px-5 py-2.5">平均相似度</th>
              </tr>
            </thead>
            <tbody>
              {stats.by_strategy.map(r => (
                <tr key={r.strategy} className="border-b border-gray-800/50">
                  <td className="px-5 py-2.5 font-mono text-indigo-400">{r.strategy}</td>
                  <td className="px-5 py-2.5 text-white">{r.hit_count}</td>
                  <td className="px-5 py-2.5 text-gray-300">{r.avg_similarity.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {stats.hits.hit_count === 0 && (
        <div className="text-center py-12 text-gray-500 text-sm">暂无缓存命中记录</div>
      )}
    </div>
  );
}
