"use client";
import {
  AreaChart as RC, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from "recharts";
import { ChartEmpty, ChartLoading, ChartWrapper, COLORS } from "./shared";

export type AreaChartProps = {
  data: Record<string, unknown>[];
  xKey: string;
  yKeys: string[];
  title?: string;
  height?: number;
  stacked?: boolean;
  smooth?: boolean;
  loading?: boolean;
  unit?: string;
  id?: string;
};

export function AreaChart({
  data, xKey, yKeys, title, height = 280, stacked, smooth, loading, unit, id,
}: AreaChartProps) {
  if (loading) return <ChartLoading height={height} />;
  if (!data.length) return <ChartEmpty height={height} />;

  return (
    <ChartWrapper title={title} id={id}>
      <ResponsiveContainer width="100%" height={height}>
        <RC data={data} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
          <defs>
            {yKeys.map((k, i) => (
              <linearGradient key={k} id={`grad-${k}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.3} />
                <stop offset="95%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.02} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey={xKey} tick={{ fill: "#9CA3AF", fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fill: "#9CA3AF", fontSize: 11 }} tickLine={false} axisLine={false} unit={unit} width={40} />
          <Tooltip
            contentStyle={{ background: "#1F2937", border: "1px solid #374151", borderRadius: 6 }}
            labelStyle={{ color: "#F9FAFB" }}
            itemStyle={{ color: "#D1D5DB" }}
          />
          {yKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11, color: "#9CA3AF" }} />}
          {yKeys.map((k, i) => (
            <Area
              key={k}
              type={smooth ? "monotone" : "linear"}
              dataKey={k}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              fill={`url(#grad-${k})`}
              stackId={stacked ? "s" : undefined}
            />
          ))}
        </RC>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}
