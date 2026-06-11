"use client";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ZAxis,
} from "recharts";
import { ChartEmpty, ChartLoading, ChartWrapper, COLORS } from "./shared";

export type ScatterPoint = { x: number; y: number; z?: number; label?: string };

export type ScatterPlotProps = {
  data: ScatterPoint[];
  title?: string;
  height?: number;
  xLabel?: string;
  yLabel?: string;
  loading?: boolean;
  id?: string;
};

export function ScatterPlot({
  data, title, height = 280, xLabel, yLabel, loading, id,
}: ScatterPlotProps) {
  if (loading) return <ChartLoading height={height} />;
  if (!data.length) return <ChartEmpty height={height} />;

  return (
    <ChartWrapper title={title} id={id}>
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            type="number" dataKey="x" name={xLabel || "x"}
            tick={{ fill: "#9CA3AF", fontSize: 11 }} tickLine={false} axisLine={false}
          />
          <YAxis
            type="number" dataKey="y" name={yLabel || "y"}
            tick={{ fill: "#9CA3AF", fontSize: 11 }} tickLine={false} axisLine={false} width={40}
          />
          <ZAxis type="number" dataKey="z" range={[40, 200]} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{ background: "#1F2937", border: "1px solid #374151", borderRadius: 6 }}
            itemStyle={{ color: "#D1D5DB" }}
            content={({ payload }) => {
              if (!payload?.length) return null;
              const p = payload[0].payload as ScatterPoint;
              return (
                <div className="bg-gray-800 border border-gray-700 rounded p-2 text-xs text-gray-300">
                  {p.label && <div className="font-medium text-white mb-1">{p.label}</div>}
                  <div>X: {p.x}</div>
                  <div>Y: {p.y}</div>
                  {p.z !== undefined && <div>Z: {p.z}</div>}
                </div>
              );
            }}
          />
          <Scatter data={data} fill={COLORS[0]} fillOpacity={0.7} />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}
