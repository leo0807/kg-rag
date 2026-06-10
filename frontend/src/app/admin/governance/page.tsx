"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { Shield, Clock, AlertTriangle, FileText, ChevronRight } from "lucide-react";

type Anomaly = { type: string; severity: string; message: string };
type Summary = { total_events: number; total_failures: number; failure_rate: number; anomalies: Anomaly[] };
type QualitySummary = { total_issues: number; severity_counts: { high: number; medium: number; low: number } };

const SEV_DOT: Record<string, string> = {
  high: "bg-red-500", medium: "bg-yellow-500", low: "bg-blue-500",
};

const MODULES = [
  { href: "/admin/audit",        icon: FileText, label: "审计日志",   desc: "查看全局操作记录" },
  { href: "/admin/permissions",  icon: Shield,   label: "权限管理",   desc: "RBAC 角色与权限" },
  { href: "/admin/lifecycle",    icon: Clock,    label: "数据生命周期", desc: "留存策略与定时清理" },
  { href: "/admin/data-quality", icon: AlertTriangle, label: "数据质量", desc: "文档质量检查" },
];

export default function GovernancePage() {
  const [report, setReport] = useState<Summary | null>(null);
  const [quality, setQuality] = useState<QualitySummary | null>(null);

  useEffect(() => {
    fetchApi<Summary>("/api/admin/compliance/report?days=7").then((d) => { if (d) setReport(d); });
    fetchApi<QualitySummary>("/api/admin/data-quality/summary").then((d) => { if (d) setQuality(d); });
  }, []);

  return (
    <div className="flex-1 overflow-y-auto bg-gray-950 p-5 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">数据治理中心</h1>
        <p className="text-sm text-gray-400 mt-0.5">合规 · 审计 · 质量 · 生命周期</p>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard label="7日事件" value={report?.total_events ?? "—"} />
        <KpiCard label="7日失败" value={report?.total_failures ?? "—"} color="text-red-400" />
        <KpiCard label="失败率" value={report ? `${report.failure_rate}%` : "—"} />
        <KpiCard label="质量问题" value={quality?.total_issues ?? "—"}
          color={(quality?.severity_counts.high ?? 0) > 0 ? "text-red-400" : "text-white"} />
      </div>

      {/* Active anomalies */}
      {report && report.anomalies.length > 0 && (
        <div className="bg-red-900/20 border border-red-700/30 rounded-lg p-4">
          <p className="text-sm font-medium text-red-400 mb-2">⚠ 实时异常 ({report.anomalies.length})</p>
          <div className="space-y-1.5">
            {report.anomalies.map((a, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className={`w-2 h-2 rounded-full shrink-0 ${SEV_DOT[a.severity] ?? "bg-gray-500"}`} />
                <span className="text-gray-300">{a.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Module links */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {MODULES.map((m) => (
          <Link key={m.href} href={m.href}
            className="flex items-center gap-4 bg-gray-900 rounded-lg p-4 border border-gray-800 hover:border-gray-600 transition-colors group">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
              <m.icon size={18} className="text-blue-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">{m.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">{m.desc}</p>
            </div>
            <ChevronRight size={16} className="text-gray-600 group-hover:text-gray-400 transition-colors" />
          </Link>
        ))}
      </div>
    </div>
  );
}

function KpiCard({ label, value, color = "text-white" }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  );
}
