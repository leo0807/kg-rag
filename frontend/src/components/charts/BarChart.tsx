"use client";
import {
  BarChart as RC, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, Cell,
} from "recharts";
import { ChartEmpty, ChartLoading, ChartWrapper, COLORS, exportChart } from "./shared";

export type BarChartProps = {
  data: Record<string, unknown>[];
  xKey: string;
  yKeys: string[];
  title?: string;
  height?: number;
  stacked?: boolean;
  horizontal?: boolean;
  loading?: boolean;
  unit?: string;
  id?: string;
};

export function BarChart({
  data, xKey, yKeys, title, height = 280, stacked, horizontal, loading, unit, id,
}: BarChartProps) {
  if (loading) return <ChartLoading height={height} />;
  if (!data.length) return <ChartEmpty height={height} />;

  const commonAxis = { tick: { fill: "#9CA3AF", fontSize: 11 }, tickLine: false, axisLine: false };

  return (
    <ChartWrapper title={title} id={id} onExport={() => exportChart(id)}>
      <ResponsiveContainer width="100%" height={height}>
        <RC
          data={data}
          layout={horizontal ? "vertical" : "horizontal"}
          margin={{ top: 4, right: 16, bottom: 0, left: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          {horizontal ? (
            <>
              <XAxis type="number" {...commonAxis} unit={unit} />
              <YAxis type="category" dataKey={xKey} {...commonAxis} width={80} />
            </>
          ) : (
            <>
              <XAxis dataKey={xKey} {...commonAxis} />
              <YAxis {...commonAxis} unit={unit} width={40} />
            </>
          )}
          <Tooltip
            contentStyle={{ background: "#1F2937", border: "1px solid #374151", borderRadius: 6 }}
            labelStyle={{ color: "#F9FAFB" }}
            itemStyle={{ color: "#D1D5DB" }}
          />
          {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: "#9CA3AF" }} />}
          {yKeys.map((k, i) => (
            <Bar key={k} dataKey={k} fill={COLORS[i % COLORS.length]} stackId={stacked ? "s" : undefined} radius={[2, 2, 0, 0]}>
              {yKeys.length === 1 && data.map((_, idx) => (
                <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
              ))}
            </Bar>
          ))}
        </RC>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}
