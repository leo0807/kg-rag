"use client";
import {
  PieChart as RC, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { ChartEmpty, ChartLoading, ChartWrapper, COLORS } from "./shared";

export type PieChartProps = {
  data: { name: string; value: number }[];
  title?: string;
  height?: number;
  donut?: boolean;
  loading?: boolean;
  id?: string;
};

const RADIAN = Math.PI / 180;
const renderLabel = ({
  cx, cy, midAngle, innerRadius, outerRadius, percent,
}: {cx: number; cy: number; midAngle: number; innerRadius: number; outerRadius: number; percent: number}) => {
  if (percent < 0.05) return null;
  const r = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={11}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

export function PieChart({ data, title, height = 280, donut, loading, id }: PieChartProps) {
  if (loading) return <ChartLoading height={height} />;
  if (!data.length) return <ChartEmpty height={height} />;

  return (
    <ChartWrapper title={title} id={id}>
      <ResponsiveContainer width="100%" height={height}>
        <RC>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={donut ? "40%" : 0}
            outerRadius="70%"
            dataKey="value"
            labelLine={false}
            label={renderLabel}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: "#1F2937", border: "1px solid #374151", borderRadius: 6 }}
            itemStyle={{ color: "#D1D5DB" }}
          />
          <Legend
            formatter={(v) => <span style={{ color: "#9CA3AF", fontSize: 11 }}>{v}</span>}
          />
        </RC>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}
