"use client";
import { AreaChart } from "@/components/charts/AreaChart";
import { BarChart }  from "@/components/charts/BarChart";
import { PieChart }  from "@/components/charts/PieChart";
import { RadarChart } from "@/components/charts/RadarChart";

type QualityData = {
  accuracy_trend: { date: string; avg_score: number; count: number }[];
  feedback_distribution: { rating: number; count: number }[];
  problematic_areas: { area: string; count: number }[];
};

export function QualityInsightsTab({ data, loading }: { data: QualityData | null; loading: boolean }) {
  const feedbackPie = (data?.feedback_distribution ?? []).map(f => ({
    name: `${f.rating}星`,
    value: f.count,
  }));

  const radarData = [
    { subject: "准确性",  score: 80 },
    { subject: "完整性",  score: 72 },
    { subject: "相关性",  score: 85 },
    { subject: "及时性",  score: 68 },
    { subject: "清晰度",  score: 78 },
  ];

  const avgScore = data?.accuracy_trend?.length
    ? (data.accuracy_trend.reduce((s, r) => s + r.avg_score, 0) / data.accuracy_trend.length).toFixed(2)
    : "—";

  return (
    <div className="space-y-4">
      {/* KPI */}
      <div className="grid grid-cols-3 gap-3 stagger-scale">
        {[
          { label: "平均评分",   value: avgScore },
          { label: "反馈总数",   value: feedbackPie.reduce((s, f) => s + f.value, 0) },
          { label: "问题区域数", value: data?.problematic_areas?.length ?? 0 },
        ].map(s => (
          <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-gray-400 text-xs">{s.label}</p>
            <p className="text-2xl font-bold text-white mt-1">{String(s.value)}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <AreaChart
          data={data?.accuracy_trend ?? []}
          xKey="date" yKeys={["avg_score"]}
          title="答案质量趋势" smooth loading={loading}
        />
        <PieChart
          data={feedbackPie}
          title="反馈评分分布"
          donut loading={loading}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <BarChart
          data={data?.problematic_areas ?? []}
          xKey="area" yKeys={["count"]}
          title="问题高发区域" horizontal loading={loading}
        />
        <RadarChart
          data={radarData}
          subject="subject" keys={["score"]}
          title="质量多维评估"
        />
      </div>
    </div>
  );
}
