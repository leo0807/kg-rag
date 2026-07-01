"use client";

import { useState, useEffect } from "react";
import { BookOpen, Layers, ImageIcon, FileText } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { LibraryListTab } from "./LibraryListTab";
import { LibraryIngestTab } from "./LibraryIngestTab";
import { LibraryReprocessTab } from "./LibraryReprocessTab";
import { SkeletonStat } from "@/components/ui/Skeleton";

interface LibraryStats { total_docs?: number; documents?: number; total_sections?: number; sections?: number; analyzed_images?: number; total_images?: number }

function KpiCard({ icon: Icon, label, value, sub, color }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color: string;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-4 flex items-center gap-3 hover-lift">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
        <Icon size={16} />
      </div>
      <div>
        <div className="text-xl font-bold text-white tabular-nums">{value}</div>
        <div className="text-xs text-gray-500">{label}</div>
        {sub && <div className="text-[10px] text-gray-700 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

function getIsAdmin() {
  try { return JSON.parse(localStorage.getItem("user") || "{}").is_admin === true; } catch { return false; }
}

export default function LibraryPage() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [activeTab, setActiveTab] = useState<"list" | "ingest" | "reprocess">("list");
  const [stats, setStats] = useState<LibraryStats | null>(null);

  useEffect(() => {
    setIsAdmin(getIsAdmin());
    const hash = window.location.hash.slice(1);
    if (hash === "ingest" || hash === "reprocess") setActiveTab(hash);
    fetchApi<LibraryStats>("/api/stats").then(setStats).catch(() => {});
  }, []);

  function switchTab(tab: "list" | "ingest" | "reprocess") {
    setActiveTab(tab);
    history.replaceState(null, "", tab === "list" ? window.location.pathname : `${window.location.pathname}#${tab}`);
  }

  const docCount = stats ? (stats.documents ?? stats.total_docs ?? 0) : null;
  const secCount = stats ? (stats.sections ?? stats.total_sections ?? 0) : null;
  const avgSec   = docCount && secCount && docCount > 0 ? Math.round(secCount / docCount) : null;

  return (
    <div className="px-4 py-4 sm:p-6 max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <BookOpen size={18} className="text-blue-400" /> 文档库
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">ATA 100 航空工艺规范知识库</p>
        </div>
      </div>

      {/* KPI row */}
      {stats === null ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => <SkeletonStat key={i} />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 stagger-scale">
          <KpiCard icon={FileText}  label="规范文档"    color="bg-blue-500/10 text-blue-400"
            value={(stats.documents ?? stats.total_docs ?? 0).toLocaleString()} />
          <KpiCard icon={Layers}    label="章节总数"    color="bg-indigo-500/10 text-indigo-400"
            value={(stats.sections ?? stats.total_sections ?? 0).toLocaleString()} />
          <KpiCard icon={ImageIcon} label="平均章节/文档" color="bg-emerald-500/10 text-emerald-400"
            value={avgSec !== null ? String(avgSec) : "—"} />
          <KpiCard icon={BookOpen}  label="知识图谱节点" color="bg-amber-500/10 text-amber-400"
            value={((stats as { total?: number }).total ?? 0).toLocaleString()} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-gray-800">
        {([
          { key: "list", label: "文档列表" },
          ...(isAdmin ? [{ key: "ingest", label: "导入文件" }] : []),
          { key: "reprocess", label: "重新处理" },
        ] as { key: typeof activeTab; label: string }[]).map(t => (
          <button key={t.key} onClick={() => switchTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === t.key
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}>{t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "ingest" && isAdmin && (
        <div className="tab-content"><LibraryIngestTab onDone={() => { switchTab("list"); }} /></div>
      )}
      {activeTab === "reprocess" && <div className="tab-content"><LibraryReprocessTab isAdmin={isAdmin} /></div>}
      {activeTab === "list" && <div className="tab-content"><LibraryListTab /></div>}
    </div>
  );
}
