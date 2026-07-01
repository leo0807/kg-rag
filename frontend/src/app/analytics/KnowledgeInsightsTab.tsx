"use client";
import { BarChart }  from "@/components/charts/BarChart";
import { TreeMap }   from "@/components/charts/TreeMap";
import { PieChart }  from "@/components/charts/PieChart";
import { FileText, Tag, Search, BarChart2 } from "lucide-react";
import { fmtNum } from "@/components/charts/shared";

type KnowledgeData = {
  hot_documents: { doc_id: string; queries: number }[];
  topic_distribution: { topic: string; count: number }[];
};

const CHART_H = 240;

export function KnowledgeInsightsTab({ data, loading }: { data: KnowledgeData | null; loading: boolean }) {
  const topicPie = (data?.topic_distribution ?? []).slice(0, 8).map(t => ({ name: t.topic, value: t.count }));
  const treemapData = (data?.topic_distribution ?? []).map(t => ({ name: t.topic, size: t.count }));
  const hotDocs = (data?.hot_documents ?? []).map(d => ({
    doc_id: d.doc_id.length > 20 ? d.doc_id.slice(0, 20) + "…" : d.doc_id,
    queries: d.queries,
  }));

  const totalQueries = (data?.hot_documents ?? []).reduce((s, d) => s + d.queries, 0);
  const topicsCount  = data?.topic_distribution?.length ?? 0;
  const hotCount     = data?.hot_documents?.length ?? 0;

  const kpis = [
    { label: "查询文档数", value: String(hotCount),           icon: FileText,  color: "text-indigo-400" },
    { label: "涉及主题数", value: String(topicsCount),        icon: Tag,       color: "text-emerald-400" },
    { label: "热门文档查询", value: fmtNum(totalQueries),     icon: Search,    color: "text-amber-400" },
    { label: "Top 话题",   value: topicPie[0]?.name ?? "—",  icon: BarChart2, color: "text-violet-400" },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        {kpis.map(s => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-3">
              <div className="shrink-0 p-2 rounded-lg bg-gray-800">
                <Icon size={16} className={s.color} />
              </div>
              <div className="min-w-0">
                <p className="text-gray-500 text-xs">{s.label}</p>
                <p className={`text-xl font-bold leading-tight truncate ${s.color}`}>{s.value}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <BarChart
          data={hotDocs}
          xKey="doc_id" yKeys={["queries"]}
          title="热门文档 Top 10" horizontal loading={loading} height={CHART_H}
        />
        <PieChart
          data={topicPie}
          title="主题分布"
          donut loading={loading} height={CHART_H}
        />
      </div>

      <TreeMap
        data={treemapData}
        title="知识主题矩阵图"
        height={220}
        loading={loading}
      />
    </div>
  );
}
