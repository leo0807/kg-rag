"use client";

export type WidgetType = "line" | "bar" | "pie" | "area" | "scatter" | "radar" | "gauge" | "treemap" | "table" | "text";

export type PaletteItem = { type: WidgetType; label: string; icon: string };

const PALETTE: PaletteItem[] = [
  { type: "line",     label: "折线图", icon: "📈" },
  { type: "bar",      label: "柱状图", icon: "📊" },
  { type: "pie",      label: "饼图",   icon: "🥧" },
  { type: "area",     label: "面积图", icon: "🌊" },
  { type: "scatter",  label: "散点图", icon: "✦" },
  { type: "radar",    label: "雷达图", icon: "🕸" },
  { type: "gauge",    label: "仪表盘", icon: "⏱" },
  { type: "treemap",  label: "矩形树图", icon: "▦" },
  { type: "table",    label: "表格",   icon: "📋" },
  { type: "text",     label: "文本",   icon: "📝" },
];

export function WidgetPalette({ onAdd }: { onAdd: (type: WidgetType) => void }) {
  return (
    <div className="w-44 bg-gray-900 border-r border-gray-800 p-3 flex flex-col gap-1">
      <p className="text-gray-500 text-xs font-medium uppercase mb-2 px-1">组件库</p>
      {PALETTE.map(item => (
        <button
          key={item.type}
          onClick={() => onAdd(item.type)}
          className="flex items-center gap-2 px-3 py-2 rounded text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors text-left w-full"
          draggable
          onDragStart={e => e.dataTransfer.setData("widget_type", item.type)}
        >
          <span>{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </div>
  );
}
