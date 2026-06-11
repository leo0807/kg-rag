"use client";
import { Treemap, ResponsiveContainer, Tooltip } from "recharts";
import { ChartEmpty, ChartLoading, ChartWrapper, COLORS } from "./shared";

export type TreeMapProps = {
  data: { name: string; size: number; children?: { name: string; size: number }[] }[];
  title?: string;
  height?: number;
  loading?: boolean;
  id?: string;
};

const CustomContent = (props: {
  x?: number; y?: number; width?: number; height?: number;
  name?: string; depth?: number; index?: number;
}) => {
  const { x = 0, y = 0, width = 0, height = 0, name = "", depth = 0, index = 0 } = props;
  if (width < 30 || height < 20) return <rect x={x} y={y} width={width} height={height} fill={COLORS[index % COLORS.length]} stroke="#111827" strokeWidth={1} />;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height}
        fill={depth === 1 ? COLORS[index % COLORS.length] : `${COLORS[index % COLORS.length]}99`}
        stroke="#111827" strokeWidth={1}
      />
      {width > 50 && height > 30 && (
        <text
          x={x + width / 2} y={y + height / 2}
          textAnchor="middle" dominantBaseline="central"
          fill="white" fontSize={Math.min(width / 6, 13)}
        >
          {name.length > 12 ? name.slice(0, 12) + "…" : name}
        </text>
      )}
    </g>
  );
};

export function TreeMap({ data, title, height = 280, loading, id }: TreeMapProps) {
  if (loading) return <ChartLoading height={height} />;
  if (!data.length) return <ChartEmpty height={height} />;

  return (
    <ChartWrapper title={title} id={id}>
      <ResponsiveContainer width="100%" height={height}>
        <Treemap
          data={data}
          dataKey="size"
          aspectRatio={4 / 3}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          content={<CustomContent /> as any}
        >
          <Tooltip
            contentStyle={{ background: "#1F2937", border: "1px solid #374151", borderRadius: 6 }}
            itemStyle={{ color: "#D1D5DB" }}
          />
        </Treemap>
      </ResponsiveContainer>
    </ChartWrapper>
  );
}
