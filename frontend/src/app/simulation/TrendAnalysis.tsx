"use client";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, LineChart, Line,
} from "recharts";

type DataPoint = { x: number; y: number; name: string; is_outlier?: boolean };

interface Props {
  points: DataPoint[];
  xLabel?: string;
  yLabel?: string;
  trendLine?: Array<{ x: number; y: number }>;
  formula?: string;
}

const OutlierTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as DataPoint;
  return (
    <div className="bg-gray-800 border border-gray-700 rounded p-2 text-xs text-white">
      <p className="font-medium">{d.name}</p>
      <p className="text-gray-400">X: {d.x}  Y: {d.y}</p>
      {d.is_outlier && <p className="text-red-400 font-medium mt-1">⚠ 异常值</p>}
    </div>
  );
};

export function TrendAnalysis({
  points,
  xLabel = "参数",
  yLabel = "结果",
  trendLine = [],
  formula,
}: Props) {
  const normal   = points.filter(p => !p.is_outlier);
  const outliers = points.filter(p =>  p.is_outlier);

  // Merge scatter + trend line for a combined view
  const combined = trendLine.map(t => ({ ...t, trend: t.y }));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-white text-sm font-medium">趋势分析</h3>
        {formula && (
          <code className="text-xs bg-gray-800 text-green-300 px-2 py-1 rounded font-mono">
            {formula}
          </code>
        )}
      </div>

      <ResponsiveContainer width="100%" height={270}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="x" name={xLabel} tick={{ fill: "#9CA3AF", fontSize: 11 }}
            label={{ value: xLabel, position: "insideBottom", offset: -10, fill: "#6B7280", fontSize: 11 }} />
          <YAxis dataKey="y" name={yLabel} tick={{ fill: "#9CA3AF", fontSize: 11 }}
            label={{ value: yLabel, angle: -90, position: "insideLeft", fill: "#6B7280", fontSize: 11 }} />
          <Tooltip content={<OutlierTooltip />} />

          {/* Normal points */}
          <Scatter name="正常案例" data={normal}  fill="#3B82F6" opacity={0.85} r={5} />

          {/* Outliers */}
          {outliers.length > 0 && (
            <Scatter name="异常值" data={outliers} fill="#EF4444" opacity={0.9}  r={7} />
          )}
        </ScatterChart>
      </ResponsiveContainer>

      {/* Trend line overlay (separate LineChart) */}
      {trendLine.length > 0 && (
        <div>
          <p className="text-gray-500 text-xs mb-1">拟合趋势线</p>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={combined} margin={{ top: 5, right: 20, bottom: 5, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="x" tick={{ fill: "#6B7280", fontSize: 10 }} />
              <YAxis tick={{ fill: "#6B7280", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#1F2937", border: "1px solid #374151", fontSize: 11 }} />
              <Line type="monotone" dataKey="trend" stroke="#F59E0B" strokeWidth={2}
                dot={false} name="趋势" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-800 rounded p-3 text-center">
          <p className="text-gray-400 text-xs">案例总数</p>
          <p className="text-white font-semibold text-lg">{points.length}</p>
        </div>
        <div className="bg-gray-800 rounded p-3 text-center">
          <p className="text-gray-400 text-xs">异常值</p>
          <p className={`font-semibold text-lg ${outliers.length > 0 ? "text-red-400" : "text-green-400"}`}>
            {outliers.length}
          </p>
        </div>
        <div className="bg-gray-800 rounded p-3 text-center">
          <p className="text-gray-400 text-xs">趋势点</p>
          <p className="text-yellow-400 font-semibold text-lg">{trendLine.length}</p>
        </div>
      </div>
    </div>
  );
}
