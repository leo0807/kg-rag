"use client";
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceDot } from "recharts";

type Point = {
  id: string;
  name: string;
  x: number;
  y: number;
  domain: string;
  confidence: string;
};

interface Props {
  points: Point[];
  xLabel?: string;
  yLabel?: string;
  gaps?: Array<{ x: number; y: number; label: string }>;
}

const DOMAIN_COLOR: Record<string, string> = {
  structural: "#3B82F6",
  thermal:    "#F59E0B",
  fluid:      "#10B981",
  coupled:    "#8B5CF6",
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as Point;
  return (
    <div className="bg-gray-800 border border-gray-700 rounded p-2 text-xs text-white shadow-lg">
      <p className="font-medium mb-1">{d.name}</p>
      <p className="text-gray-400">X: {d.x}  Y: {d.y}</p>
      <p className="text-gray-400">{d.domain} · {d.confidence}</p>
    </div>
  );
};

export function ParameterSpace({ points, xLabel = "参数 X", yLabel = "参数 Y", gaps = [] }: Props) {
  // Group by domain for multi-scatter series
  const domains = Array.from(new Set(points.map(p => p.domain)));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white text-sm font-medium">参数空间分布</h3>
        {/* Domain legend */}
        <div className="flex gap-3">
          {domains.map(d => (
            <span key={d} className="flex items-center gap-1 text-xs text-gray-400">
              <span className="w-2 h-2 rounded-full" style={{ background: DOMAIN_COLOR[d] ?? "#6B7280" }} />
              {d}
            </span>
          ))}
          {gaps.length > 0 && (
            <span className="flex items-center gap-1 text-xs text-red-400">
              <span className="w-2 h-2 rounded-full bg-red-400" />
              建议补充
            </span>
          )}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="x" name={xLabel} tick={{ fill: "#9CA3AF", fontSize: 11 }}
            label={{ value: xLabel, position: "insideBottom", offset: -10, fill: "#6B7280", fontSize: 11 }} />
          <YAxis dataKey="y" name={yLabel} tick={{ fill: "#9CA3AF", fontSize: 11 }}
            label={{ value: yLabel, angle: -90, position: "insideLeft", fill: "#6B7280", fontSize: 11 }} />
          <Tooltip content={<CustomTooltip />} />

          {domains.map(d => (
            <Scatter
              key={d}
              name={d}
              data={points.filter(p => p.domain === d)}
              fill={DOMAIN_COLOR[d] ?? "#6B7280"}
              opacity={0.85}
              r={5}
            />
          ))}

          {gaps.map((g, i) => (
            <ReferenceDot key={i} x={g.x} y={g.y} r={8}
              fill="none" stroke="#EF4444" strokeWidth={2} strokeDasharray="4 2"
              label={{ value: g.label, fill: "#EF4444", fontSize: 10 }} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>

      {gaps.length > 0 && (
        <div className="mt-3 p-3 bg-red-950 border border-red-800 rounded text-xs text-red-300">
          <span className="font-medium">建议补充仿真区域：</span>{" "}
          {gaps.map(g => g.label).join("、")}
        </div>
      )}

      {points.length === 0 && (
        <div className="text-center text-gray-500 py-6 text-sm">无数据，检索后显示参数分布</div>
      )}
    </div>
  );
}
