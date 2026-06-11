"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

const AUTH = () => `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") : ""}`;

type Stats = {
  total: number; pending_review: number; running_workflows: number;
  domain_dist: Record<string, number>; software_dist: Record<string, number>;
  pass_rate: number; rules_applied: number;
  recent: Array<{ id: string; case_name: string; domain: string; confidence_level: string; created_at: string }>;
};

const DOMAIN_COLOR: Record<string, string> = {
  structural: "#3B82F6", thermal: "#F59E0B", fluid: "#10B981", coupled: "#8B5CF6"
};
const PALETTE = ["#3B82F6","#F59E0B","#10B981","#8B5CF6","#EF4444","#EC4899"];

const NAV = [
  { href: "/simulation",           icon: "📚", label: "案例库",    desc: "浏览与管理仿真案例" },
  { href: "/simulation/search",    icon: "📈", label: "参数化查询", desc: "按物理参数精确检索" },
  { href: "/simulation/compare",   icon: "🔬", label: "案例对比",  desc: "并排对比 2-4 个案例" },
  { href: "/simulation/workflows", icon: "🔄", label: "工作流",    desc: "DOE 扫掠 · 集群提交" },
];

export default function SimDashboard() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    fetch("/api/simulation/stats", { headers: { Authorization: AUTH() } })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setStats(d));
  }, []);

  const domainData = stats
    ? Object.entries(stats.domain_dist).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div className="p-6 max-w-7xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">仿真中心</h1>
        <p className="text-gray-400 text-sm mt-1">CAE/CFD 仿真数据管理 · 规范+经验+仿真三位一体</p>
      </div>

      {/* Navigation cards */}
      <div className="grid grid-cols-4 gap-4">
        {NAV.map(n => (
          <Link key={n.href} href={n.href}
            className="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-colors group">
            <div className="text-3xl mb-3">{n.icon}</div>
            <p className="text-white font-medium text-sm group-hover:text-blue-300 transition-colors">{n.label}</p>
            <p className="text-gray-500 text-xs mt-1">{n.desc}</p>
          </Link>
        ))}
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "案例总数", value: stats?.total ?? "—", color: "text-blue-400" },
          { label: "待审核",   value: stats?.pending_review ?? "—", color: "text-yellow-400" },
          { label: "运行中工作流", value: stats?.running_workflows ?? "—", color: "text-green-400" },
          { label: "规则应用次数", value: stats?.rules_applied ?? "—", color: "text-purple-400" },
        ].map((k, i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
            <p className="text-gray-500 text-xs mb-1">{k.label}</p>
            <p className={`text-2xl font-bold ${k.color}`}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Main content: recent + charts */}
      <div className="grid grid-cols-2 gap-5">
        {/* Recent cases */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div className="px-4 py-3 bg-gray-800 flex items-center justify-between">
            <span className="text-white text-sm font-medium">最近案例</span>
            <Link href="/simulation" className="text-blue-400 text-xs hover:underline">全部 →</Link>
          </div>
          <div className="divide-y divide-gray-800">
            {(stats?.recent ?? []).slice(0, 5).map(c => (
              <Link key={c.id} href={`/simulation/${c.id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-gray-800 transition-colors">
                <div>
                  <p className="text-white text-sm">{c.case_name}</p>
                  <p className="text-gray-500 text-xs">{c.domain}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  c.confidence_level === "已验证" ? "bg-green-900 text-green-300" :
                  c.confidence_level === "参考"   ? "bg-blue-900 text-blue-300" :
                  "bg-yellow-900 text-yellow-300"
                }`}>{c.confidence_level}</span>
              </Link>
            ))}
            {!stats && [1,2,3].map(i => (
              <div key={i} className="px-4 py-3 animate-pulse">
                <div className="h-4 bg-gray-800 rounded w-3/4 mb-1" />
                <div className="h-3 bg-gray-800 rounded w-1/3" />
              </div>
            ))}
          </div>
        </div>

        {/* Domain pie chart */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-white text-sm font-medium mb-3">各物理域分布</h3>
          {domainData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={domainData} dataKey="value" nameKey="name"
                    cx="50%" cy="50%" innerRadius={45} outerRadius={70}>
                    {domainData.map((entry, i) => (
                      <Cell key={i} fill={DOMAIN_COLOR[entry.name] ?? PALETTE[i % PALETTE.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#1F2937", border: "1px solid #374151", fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-2 justify-center mt-2">
                {domainData.map((d, i) => (
                  <span key={i} className="flex items-center gap-1 text-xs text-gray-400">
                    <span className="w-2 h-2 rounded-full"
                      style={{ background: DOMAIN_COLOR[d.name] ?? PALETTE[i % PALETTE.length] }} />
                    {d.name}: {d.value}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <div className="text-center text-gray-600 py-12 text-sm">暂无数据</div>
          )}
        </div>
      </div>

      {/* Pass rate */}
      {stats && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-white text-sm font-medium">仿真结果通过率</span>
            <span className="text-2xl font-bold text-green-400">{(stats.pass_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-2">
            <div className="bg-green-500 h-2 rounded-full transition-all"
              style={{ width: `${stats.pass_rate * 100}%` }} />
          </div>
        </div>
      )}
    </div>
  );
}
