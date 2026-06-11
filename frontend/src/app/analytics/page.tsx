"use client";
import { useEffect, useState } from "react";
import { UsageInsightsTab }      from "./UsageInsightsTab";
import { QualityInsightsTab }    from "./QualityInsightsTab";
import { KnowledgeInsightsTab }  from "./KnowledgeInsightsTab";
import { OperationsInsightsTab } from "./OperationsInsightsTab";

const TABS = ["使用情况", "答案质量", "知识使用", "运营指标"] as const;
type Tab = typeof TABS[number];

const PERIODS = ["7d", "30d", "90d", "1y"] as const;
type Period = typeof PERIODS[number];

const AUTH = () => `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") : ""}`;

export default function AnalyticsPage() {
  const [tab, setTab]       = useState<Tab>("使用情况");
  const [period, setPeriod] = useState<Period>("30d");
  const [data, setData]     = useState<Record<Tab, unknown | null>>({
    "使用情况": null, "答案质量": null, "知识使用": null, "运营指标": null,
  });
  const [loading, setLoading] = useState(false);

  const ENDPOINTS: Record<Tab, string> = {
    "使用情况": "usage",
    "答案质量": "quality",
    "知识使用": "knowledge",
    "运营指标": "operations",
  };

  const load = async (t: Tab) => {
    if (data[t]) return;
    setLoading(true);
    try {
      const r = await fetch(`/api/analytics/${ENDPOINTS[t]}?period=${period}`, {
        headers: { Authorization: AUTH() },
      });
      const d = await r.json();
      setData(prev => ({ ...prev, [t]: d }));
    } finally {
      setLoading(false);
    }
  };

  const reload = async () => {
    setData({ "使用情况": null, "答案质量": null, "知识使用": null, "运营指标": null });
    setLoading(true);
    try {
      const r = await fetch(`/api/analytics/${ENDPOINTS[tab]}?period=${period}`, {
        headers: { Authorization: AUTH() },
      });
      const d = await r.json();
      setData(prev => ({ ...prev, [tab]: d }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(tab); }, [tab, period]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">数据洞察中心</h1>
          <p className="text-gray-400 text-sm mt-1">全面了解系统运行状态与业务价值</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Period selector */}
          <div className="flex rounded-lg overflow-hidden border border-gray-700">
            {PERIODS.map(p => (
              <button
                key={p}
                onClick={() => { setPeriod(p); setData(prev => ({ ...prev, [tab]: null })); }}
                className={`px-3 py-1.5 text-xs ${period === p ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"}`}
              >
                {p}
              </button>
            ))}
          </div>
          <button onClick={reload} disabled={loading}
            className="bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs px-3 py-1.5 rounded border border-gray-700">
            {loading ? "加载中…" : "刷新"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-800">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-5 py-2.5 text-sm border-b-2 transition-colors ${
              tab === t
                ? "border-blue-500 text-white"
                : "border-transparent text-gray-400 hover:text-white"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "使用情况" && (
        <UsageInsightsTab data={data["使用情况"] as Parameters<typeof UsageInsightsTab>[0]["data"]} loading={loading} />
      )}
      {tab === "答案质量" && (
        <QualityInsightsTab data={data["答案质量"] as Parameters<typeof QualityInsightsTab>[0]["data"]} loading={loading} />
      )}
      {tab === "知识使用" && (
        <KnowledgeInsightsTab data={data["知识使用"] as Parameters<typeof KnowledgeInsightsTab>[0]["data"]} loading={loading} />
      )}
      {tab === "运营指标" && (
        <OperationsInsightsTab data={data["运营指标"] as Parameters<typeof OperationsInsightsTab>[0]["data"]} loading={loading} />
      )}
    </div>
  );
}
