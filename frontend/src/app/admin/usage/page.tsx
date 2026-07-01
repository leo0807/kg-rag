"use client";

import { useEffect, useRef, useState } from "react";
import { Activity, Clock, DollarSign, RefreshCw, Zap } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { UserUsageTable } from "./UserUsageTable";
import { FeedbackStatsPanel } from "./FeedbackStatsPanel";
import { PerformanceTrendPanel } from "./PerformanceTrendPanel";
import { ModelDistributionChart, fmtTokens, shortModel } from "./ModelDistributionChart";
import { TrendLineChart } from "./TrendLineChart";

interface PeriodStats { requests: number; input_tokens: number; output_tokens: number; avg_latency_ms: number; cost_usd: number }
interface ModelItem   { model: string; requests: number; tokens: number; cost_usd: number }
interface TrendItem   { date: string; requests: number; tokens: number; cost_usd: number; avg_latency_ms?: number }
interface UsageData {
  today: PeriodStats; week: PeriodStats;
  model_distribution: ModelItem[]; daily_trend: TrendItem[];
  sources: { langfuse_available: boolean; pg_records_today: number };
}

function fmtMs(ms: number): string {
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`;
  if (ms >= 1_000)  return `${(ms / 1_000).toFixed(1)}s`;
  return `${ms}ms`;
}

function MetricCard({ icon: Icon, label, value, sub, color = "indigo" }: {
  icon: React.ElementType; label: string; value: string; sub?: string;
  color?: "indigo" | "amber" | "emerald" | "cyan";
}) {
  const ring: Record<string, string> = {
    indigo:  "ring-indigo-500/30 bg-indigo-500/10 text-indigo-400",
    amber:   "ring-amber-500/30  bg-amber-500/10  text-amber-400",
    emerald: "ring-emerald-500/30 bg-emerald-500/10 text-emerald-400",
    cyan:    "ring-cyan-500/30   bg-cyan-500/10   text-cyan-400",
  };
  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-900 p-5 flex items-start gap-4">
      <div className={`rounded-xl ring-1 p-2.5 shrink-0 ${ring[color]}`}><Icon size={18} /></div>
      <div className="min-w-0">
        <div className="text-xs text-gray-500 mb-1">{label}</div>
        <div className="text-2xl font-semibold text-white truncate">{value}</div>
        {sub && <div className="text-xs text-gray-500 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

export default function UsagePage() {
  const [data, setData]           = useState<UsageData | null>(null);
  const [loading, setLoading]     = useState(true);
  const [lastRefresh, setLast]    = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function load() {
    try {
      const d = await fetchApi<UsageData>("/api/admin/usage");
      setData(d); setLast(new Date());
    } catch (e) { console.error("usage fetch failed", e); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    load();
    timerRef.current = setInterval(load, 60_000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  const today   = data?.today;
  const week    = data?.week;
  const pieData = (data?.model_distribution ?? []).map(m => ({
    name: shortModel(m.model), value: m.requests, tokens: m.tokens,
  }));
  const trend   = data?.daily_trend ?? [];

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
      <div className="rounded-3xl border border-gray-800 bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.18),transparent_42%),radial-gradient(circle_at_top_right,rgba(16,185,129,0.1),transparent_36%),#111827] p-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
              <Zap size={22} className="text-indigo-400" /> Token 用量监控
            </h1>
            <p className="mt-1 text-sm text-gray-400">数据来源：Langfuse + 本地 LLMUsage 表，每 60 秒自动刷新</p>
          </div>
          <div className="flex items-center gap-3">
            {data?.sources?.langfuse_available && (
              <span className="text-xs px-2 py-1 rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                Langfuse 已连接
              </span>
            )}
            {lastRefresh && (
              <span className="text-xs text-gray-500">{lastRefresh.toLocaleTimeString("zh-CN")} 更新</span>
            )}
            <button type="button" onClick={() => { setLoading(true); load(); }} disabled={loading}
              className="inline-flex items-center gap-2 px-3 h-9 rounded-xl border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors disabled:opacity-50">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> 刷新
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard icon={Activity} label="今日请求数" value={loading ? "—" : String(today?.requests ?? 0)}
          sub={`本周共 ${week?.requests ?? 0} 次`} color="indigo" />
        <MetricCard icon={Zap} label="今日 Token"
          value={loading ? "—" : fmtTokens((today?.input_tokens ?? 0) + (today?.output_tokens ?? 0))}
          sub={`↑ ${fmtTokens(today?.input_tokens ?? 0)} 输入  ↓ ${fmtTokens(today?.output_tokens ?? 0)} 输出`}
          color="amber" />
        <MetricCard icon={DollarSign} label="今日费用估算"
          value={loading ? "—" : `$${(today?.cost_usd ?? 0).toFixed(4)}`}
          sub={`本周 $${(week?.cost_usd ?? 0).toFixed(4)}`} color="emerald" />
        <MetricCard icon={Clock} label="平均响应时间"
          value={loading ? "—" : fmtMs(today?.avg_latency_ms ?? 0)}
          sub={`本周均值 ${fmtMs(week?.avg_latency_ms ?? 0)}`} color="cyan" />
      </div>

      <div className="grid xl:grid-cols-2 gap-6">
        <div className="rounded-3xl border border-gray-800 bg-gray-900 p-5">
          <div className="text-white font-medium mb-4">模型调用分布（近 7 天）</div>
          <ModelDistributionChart data={pieData} />
        </div>
        <div className="rounded-3xl border border-gray-800 bg-gray-900 p-5">
          <div className="text-white font-medium mb-4">7 天 Token 趋势</div>
          <TrendLineChart trend={trend} />
        </div>
      </div>

      {(data?.model_distribution ?? []).length > 0 && (
        <div className="rounded-3xl border border-gray-800 bg-gray-900 p-5">
          <div className="text-white font-medium mb-4">模型用量明细（近 7 天）</div>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="text-gray-400 text-left">
                <tr>
                  <th className="pb-3 pr-6">模型</th>
                  <th className="pb-3 pr-6">请求次数</th>
                  <th className="pb-3 pr-6">Token 总量</th>
                  <th className="pb-3">费用估算（USD）</th>
                </tr>
              </thead>
              <tbody className="text-gray-300">
                {data!.model_distribution.map(m => (
                  <tr key={m.model} className="border-t border-gray-800">
                    <td className="py-2.5 pr-6 font-mono text-xs text-gray-400">{m.model}</td>
                    <td className="py-2.5 pr-6">{(m.requests ?? 0).toLocaleString()}</td>
                    <td className="py-2.5 pr-6">{fmtTokens(m.tokens)}</td>
                    <td className="py-2.5">${(m.cost_usd ?? 0).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <PerformanceTrendPanel trend={trend} />
      <UserUsageTable />
      <FeedbackStatsPanel />
    </div>
  );
}
