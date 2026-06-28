"use client";
import { BarChart }  from "@/components/charts/BarChart";
import { TreeMap }   from "@/components/charts/TreeMap";
import { PieChart }  from "@/components/charts/PieChart";

type KnowledgeData = {
  hot_documents: { doc_id: string; queries: number }[];
  topic_distribution: { topic: string; count: number }[];
};

export function KnowledgeInsightsTab({ data, loading }: { data: KnowledgeData | null; loading: boolean }) {
  const topicPie = (data?.topic_distribution ?? []).slice(0, 8).map(t => ({
    name: t.topic,
    value: t.count,
  }));

  const treemapData = (data?.topic_distribution ?? []).map(t => ({
    name: t.topic,
    size: t.count,
  }));

  const hotDocs = (data?.hot_documents ?? []).map(d => ({
    doc_id: d.doc_id.length > 20 ? d.doc_id.slice(0, 20) + "…" : d.doc_id,
    queries: d.queries,
  }));

  const totalQueries = (data?.hot_documents ?? []).reduce((s, d) => s + d.queries, 0);
  const topicsCount  = data?.topic_distribution?.length ?? 0;
  const hotCount     = data?.hot_documents?.length ?? 0;

  return (
    <div className="space-y-4">
      {/* KPI */}
      <div className="grid grid-cols-3 gap-3 stagger-scale">
        {[
          { label: "总查询文档数", value: hotCount },
          { label: "涉及主题数",   value: topicsCount },
          { label: "热门文档查询", value: totalQueries },
        ].map(s => (
          <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-gray-400 text-xs">{s.label}</p>
            <p className="text-2xl font-bold text-white mt-1">{String(s.value)}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <BarChart
          data={hotDocs}
          xKey="doc_id" yKeys={["queries"]}
          title="热门文档 Top 10" horizontal loading={loading}
        />
        <PieChart
          data={topicPie}
          title="主题分布"
          donut loading={loading}
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
