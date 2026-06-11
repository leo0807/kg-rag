"use client";
import { WidgetType } from "./WidgetPalette";

export type WidgetConfig = {
  id: string;
  type: WidgetType;
  title?: string;
  endpoint?: string;
  xKey?: string;
  yKeys?: string;
  refresh?: number;
  height?: number;
};

const INPUT = "w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500";
const LABEL = "block text-xs text-gray-400 mb-1 mt-3 first:mt-0";

type Props = {
  widget: WidgetConfig | null;
  onChange: (w: WidgetConfig) => void;
};

export function PropertyPanel({ widget, onChange }: Props) {
  if (!widget) {
    return (
      <div className="w-56 bg-gray-900 border-l border-gray-800 p-4 flex items-center justify-center">
        <p className="text-gray-600 text-xs text-center">选中画布中的组件<br/>以编辑属性</p>
      </div>
    );
  }

  const set = (key: keyof WidgetConfig) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange({ ...widget, [key]: e.target.value });

  return (
    <div className="w-56 bg-gray-900 border-l border-gray-800 p-4 overflow-y-auto">
      <p className="text-white text-xs font-medium mb-4">属性配置</p>

      <label className={LABEL}>标题</label>
      <input className={INPUT} value={widget.title ?? ""} onChange={set("title")} placeholder="图表标题" />

      <label className={LABEL}>数据端点 (API path)</label>
      <input className={INPUT} value={widget.endpoint ?? ""} onChange={set("endpoint")} placeholder="/api/analytics/usage" />

      {["line", "bar", "area", "scatter"].includes(widget.type) && (
        <>
          <label className={LABEL}>X 轴字段</label>
          <input className={INPUT} value={widget.xKey ?? ""} onChange={set("xKey")} placeholder="date" />

          <label className={LABEL}>Y 轴字段（逗号分隔）</label>
          <input className={INPUT} value={widget.yKeys ?? ""} onChange={set("yKeys")} placeholder="queries,errors" />
        </>
      )}

      <label className={LABEL}>高度 (px)</label>
      <input
        className={INPUT}
        type="number"
        value={widget.height ?? 240}
        onChange={e => onChange({ ...widget, height: Number(e.target.value) })}
      />

      <label className={LABEL}>刷新间隔 (秒，0=不刷新)</label>
      <input
        className={INPUT}
        type="number"
        value={widget.refresh ?? 0}
        onChange={e => onChange({ ...widget, refresh: Number(e.target.value) })}
      />

      <p className="text-gray-600 text-xs mt-4">类型: <span className="text-gray-400">{widget.type}</span></p>
      <p className="text-gray-600 text-xs">ID: <span className="text-gray-400 font-mono text-[10px]">{widget.id}</span></p>
    </div>
  );
}
