"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { FeedbackStats } from "./FeedbackStats";
import { ErrorCaseList } from "./ErrorCaseList";
import { ProblematicChunks } from "./ProblematicChunks";

interface OverviewStats {
  total:      number;
  positive:   number;
  negative:   number;
  avg_rating: number | null;
  accuracy_dist:   Record<string, number>;
  error_type_dist: Record<string, number>;
}

interface ErrorCase {
  id: number; question: string; answer: string;
  rating: number; accuracy: string | null;
  error_types: string[]; correct_answer: string | null;
  comment: string | null; strategy: string;
  status: string; created_at: string;
}

interface ChunkItem {
  chunk_id: string; total: number; errors: number; error_rate: number;
}

type Tab = "overview" | "errors" | "chunks";

export default function FeedbackAdminPage() {
  const [stats,    setStats]    = useState<OverviewStats | null>(null);
  const [cases,    setCases]    = useState<ErrorCase[]>([]);
  const [chunks,   setChunks]   = useState<ChunkItem[]>([]);
  const [loading,  setLoading]  = useState(false);
  const [tab,      setTab]      = useState<Tab>("overview");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, casesData, chunksData] = await Promise.all([
        fetchApi<OverviewStats>("/api/admin/feedback/overview-stats"),
        fetchApi<{ items: ErrorCase[] }>("/api/admin/feedback/error-cases?limit=100"),
        fetchApi<{ items: ChunkItem[] }>("/api/admin/feedback/problematic-chunks?limit=10"),
      ]);
      setStats(statsData);
      setCases(casesData.items);
      setChunks(chunksData.items);
    } catch {
      // errors are shown inline
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleResolve(feedbackId: number) {
    await fetchApi("/api/admin/feedback/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ feedback_id: feedbackId }),
    });
    setCases(prev => prev.map(c => c.id === feedbackId ? { ...c, status: "resolved" } : c));
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: "overview", label: "概览" },
    { key: "errors",   label: `错误案例${cases.length > 0 ? ` (${cases.length})` : ""}` },
    { key: "chunks",   label: `高错误率章节${chunks.length > 0 ? ` (${chunks.length})` : ""}` },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white">反馈分析</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            用户反馈数据驱动系统持续改进
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 text-gray-400 text-xs rounded-lg hover:text-white transition-colors disabled:opacity-40"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          刷新
        </button>
      </div>

      {/* 标签页 */}
      <div className="flex gap-1 border-b border-gray-800">
        {TABS.map(t => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-px ${
              tab === t.key
                ? "border-[#1B6BB5] text-[#1B6BB5]"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <FeedbackStats data={stats} loading={loading} />
      )}

      {tab === "errors" && (
        <div className="space-y-4">
          <div className="text-xs text-gray-500">
            显示所有负面评价和错误标注案例，支持按错误类型筛选
          </div>
          <ErrorCaseList items={cases} loading={loading} onResolve={handleResolve} />
        </div>
      )}

      {tab === "chunks" && (
        <div className="space-y-4">
          <div className="text-xs text-gray-500">
            基于来源引用分析，展示高错误率章节（需 ≥2 个样本）
          </div>
          <ProblematicChunks items={chunks} loading={loading} />
        </div>
      )}
    </div>
  );
}
