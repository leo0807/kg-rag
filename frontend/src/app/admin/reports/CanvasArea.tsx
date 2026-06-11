"use client";
import { useState } from "react";
import { WidgetConfig } from "./PropertyPanel";
import { WidgetType } from "./WidgetPalette";
import { LineChart } from "@/components/charts/LineChart";
import { BarChart }  from "@/components/charts/BarChart";
import { PieChart }  from "@/components/charts/PieChart";
import { AreaChart } from "@/components/charts/AreaChart";
import { RadarChart } from "@/components/charts/RadarChart";
import { Gauge }     from "@/components/charts/Gauge";
import { TreeMap }   from "@/components/charts/TreeMap";

type Props = {
  widgets: WidgetConfig[];
  selected: string | null;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
  onDrop: (type: WidgetType) => void;
};

function WidgetPreview({ w }: { w: WidgetConfig }) {
  const h = w.height ?? 180;
  const yKeys = (w.yKeys ?? "value").split(",").map(s => s.trim());
  const empty = [{ date: "暂无数据", value: 0 }];

  if (w.type === "line")    return <LineChart data={empty} xKey="date" yKeys={yKeys} height={h} />;
  if (w.type === "bar")     return <BarChart  data={empty} xKey="date" yKeys={yKeys} height={h} />;
  if (w.type === "area")    return <AreaChart data={empty} xKey="date" yKeys={yKeys} height={h} />;
  if (w.type === "pie")     return <PieChart  data={[{ name: "示例", value: 1 }]} height={h} />;
  if (w.type === "radar")   return <RadarChart data={[]} subject="subject" keys={[]} height={h} />;
  if (w.type === "gauge")   return <Gauge value={65} title={w.title} size={120} />;
  if (w.type === "treemap") return <TreeMap data={[{ name: "示例", size: 1 }]} height={h} />;
  if (w.type === "table")   return (
    <div className="bg-gray-900 border border-gray-700 rounded p-3 text-xs text-gray-400" style={{ height: h }}>
      表格预览（连接数据源后展示）
    </div>
  );
  if (w.type === "text")    return (
    <div className="bg-gray-900 border border-gray-700 rounded p-3 text-sm text-gray-300" style={{ height: h }}>
      {w.title || "文本内容"}
    </div>
  );
  return null;
}

export function CanvasArea({ widgets, selected, onSelect, onRemove, onDrop }: Props) {
  const [dragOver, setDragOver] = useState(false);

  return (
    <div
      className={`flex-1 bg-gray-950 overflow-auto p-4 transition-colors ${dragOver ? "bg-gray-900" : ""}`}
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={e => {
        e.preventDefault();
        setDragOver(false);
        const t = e.dataTransfer.getData("widget_type") as WidgetType;
        if (t) onDrop(t);
      }}
    >
      {widgets.length === 0 && (
        <div className="flex items-center justify-center h-full min-h-64 border-2 border-dashed border-gray-700 rounded-lg">
          <p className="text-gray-500 text-sm">从左侧拖拽组件到此处，或点击组件名称添加</p>
        </div>
      )}
      <div className="grid grid-cols-2 gap-4">
        {widgets.map(w => (
          <div
            key={w.id}
            onClick={() => onSelect(w.id)}
            className={`relative cursor-pointer rounded-lg transition-all ${
              selected === w.id ? "ring-2 ring-blue-500" : "hover:ring-1 hover:ring-gray-600"
            }`}
          >
            {/* Title overlay */}
            {w.title && (
              <div className="absolute top-2 left-3 z-10 text-white text-xs font-medium pointer-events-none">
                {w.title}
              </div>
            )}
            {/* Remove button */}
            <button
              onClick={e => { e.stopPropagation(); onRemove(w.id); }}
              className="absolute top-2 right-2 z-10 text-gray-500 hover:text-red-400 text-xs bg-gray-900 rounded px-1"
            >
              ✕
            </button>
            <WidgetPreview w={w} />
          </div>
        ))}
      </div>
    </div>
  );
}
