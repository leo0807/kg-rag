"use client";
import {
  LineChart as RC, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from "recharts";
import { ChartEmpty, ChartLoading, ChartWrapper, COLORS, exportChart } from "./shared";

export type LineChartProps = {
  data: Record<string, unknown>[];
  xKey: string;
  yKeys: string[];
  title?: string;
  height?: number;
  smooth?: boolean;
  stacked?: boolean;
  loading?: boolean;
  unit?: string;
  id?: string;
};

export function LineChart({
  data, xKey, yKeys, title, height = 280, smooth, loading, unit, id,
}: LineChartProps) {
  if (loading) return <ChartLoading height={height} />;
  if (!data.length) return <ChartEmpty height={height} />;

  return (
    <ChartWrapper title={title} id={id} onExport={() => exportChart(id)}>
      <ResponsiveContainer width="100%" height={height}>
        <RC data={data} margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
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
            <Line
              key={k}
              type={smooth ? "monotone" : "linear"}
              dataKey={k}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </RC>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}
