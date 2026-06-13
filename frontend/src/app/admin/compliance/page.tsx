"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

type CheckItem = { name: string; passed: boolean; detail: string; severity: string };
type Category  = { category: string; score: number; passed: number; total: number; items: CheckItem[] };
type Report    = { overall_score: number; failed_critical: number; generated_at: number; categories: Category[] };

const SEV_COLOR: Record<string, string> = {
  critical: "text-red-400",
  high:     "text-orange-400",
  medium:   "text-yellow-400",
  low:      "text-blue-400",
};

const ScoreRing = ({ score }: { score: number }) => {
  const color = score >= 80 ? "text-green-400" : score >= 60 ? "text-yellow-400" : "text-red-400";
  return (
    <div className={`text-5xl font-bold ${color}`}>{score}<span className="text-2xl text-gray-400">%</span></div>
  );
};

export default function CompliancePage() {
  const [report, setReport]   = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    try {
      setReport(await fetchApi("/api/admin/security/compliance"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { run(); }, []);

  const fmtTime = (ts: number) => new Date(ts * 1000).toLocaleString("zh-CN");

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">等保2.0 合规仪表盘</h1>
          <p className="text-gray-400 text-sm mt-1">三级等保控制项自动检查</p>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded"
        >
          {loading ? "检查中…" : "重新检查"}
        </button>
      </div>

      {loading && !report && (
        <div className="text-center text-gray-400 py-16 text-sm">正在运行合规检查…</div>
      )}

      {report && (
        <>
          {/* Overall score */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 flex flex-col items-center">
              <p className="text-gray-400 text-xs mb-2">综合评分</p>
              <ScoreRing score={report.overall_score} />
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 flex flex-col items-center">
              <p className="text-gray-400 text-xs mb-2">严重未通过项</p>
              <div className={`text-5xl font-bold ${report.failed_critical > 0 ? "text-red-400" : "text-green-400"}`}>
                {report.failed_critical}
              </div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 flex flex-col items-center">
              <p className="text-gray-400 text-xs mb-2">检查时间</p>
              <p className="text-white text-sm mt-1">{fmtTime(report.generated_at)}</p>
            </div>
          </div>

          {/* Category breakdown */}
          <div className="space-y-3">
            {report.categories.map(cat => (
              <div key={cat.category} className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
                <button
                  className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800 transition-colors"
                  onClick={() => setExpanded(expanded === cat.category ? null : cat.category)}
                >
                  <div className="flex items-center gap-4">
                    <span className="text-white font-medium text-sm">{cat.category}</span>
                    <span className="text-gray-400 text-xs">{cat.passed}/{cat.total} 通过</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-24 bg-gray-700 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${cat.score >= 80 ? "bg-green-500" : cat.score >= 60 ? "bg-yellow-500" : "bg-red-500"}`}
                        style={{ width: `${cat.score}%` }}
                      />
                    </div>
                    <span className={`text-sm font-medium ${cat.score >= 80 ? "text-green-400" : cat.score >= 60 ? "text-yellow-400" : "text-red-400"}`}>
                      {cat.score}%
                    </span>
                    <span className="text-gray-500 text-xs">{expanded === cat.category ? "▲" : "▼"}</span>
                  </div>
                </button>

                {expanded === cat.category && (
                  <div className="border-t border-gray-800">
                    <table className="w-full text-sm">
                      <tbody>
                        {cat.items.map(item => (
                          <tr key={item.name} className="border-b border-gray-800 last:border-0">
                            <td className="px-5 py-3 w-8">
                              <span className={item.passed ? "text-green-400" : "text-red-400"}>
                                {item.passed ? "✓" : "✗"}
                              </span>
                            </td>
                            <td className="py-3 text-white">{item.name}</td>
                            <td className={`py-3 px-3 text-xs ${SEV_COLOR[item.severity] || "text-gray-400"}`}>
                              {item.severity}
                            </td>
                            <td className="py-3 pr-5 text-gray-400 text-xs">{item.detail}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
