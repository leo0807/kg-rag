"use client";
import {
  RadarChart as RC, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip,
} from "recharts";
import { ChartEmpty, ChartLoading, ChartWrapper, COLORS } from "./shared";

export type RadarChartProps = {
  data: Record<string, unknown>[];
  subject: string;       // the angle-axis key
  keys: string[];        // data keys to plot
  title?: string;
  height?: number;
  loading?: boolean;
  id?: string;
};

export function RadarChart({
  data, subject, keys, title, height = 280, loading, id,
}: RadarChartProps) {
  if (loading) return <ChartLoading height={height} />;
  if (!data.length) return <ChartEmpty height={height} />;

  return (
    <ChartWrapper title={title} id={id}>
      <ResponsiveContainer width="100%" height={height}>
        <RC data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <PolarGrid stroke="#374151" />
          <PolarAngleAxis dataKey={subject} tick={{ fill: "#9CA3AF", fontSize: 11 }} />
          <PolarRadiusAxis tick={{ fill: "#6B7280", fontSize: 10 }} tickCount={4} />
          <Tooltip
            contentStyle={{ background: "#1F2937", border: "1px solid #374151", borderRadius: 6 }}
            itemStyle={{ color: "#D1D5DB" }}
          />
          {keys.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: "#9CA3AF" }} />}
          {keys.map((k, i) => (
            <Radar
              key={k}
              name={k}
              dataKey={k}
              stroke={COLORS[i % COLORS.length]}
              fill={COLORS[i % COLORS.length]}
              fillOpacity={0.15}
              strokeWidth={2}
            />
          ))}
        </RC>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}
