"use client";
import { useState } from "react";
import { WidgetPalette, WidgetType } from "./WidgetPalette";
import { CanvasArea } from "./CanvasArea";
import { PropertyPanel, WidgetConfig } from "./PropertyPanel";

type Props = {
  initialWidgets?: WidgetConfig[];
  reportName?: string;
  onSave: (name: string, widgets: WidgetConfig[]) => void;
};

let _id = 0;
const newId = () => `w-${Date.now()}-${_id++}`;

export function ReportBuilder({ initialWidgets = [], reportName = "", onSave }: Props) {
  const [widgets, setWidgets]   = useState<WidgetConfig[]>(initialWidgets);
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName]         = useState(reportName);
  const [saving, setSaving]     = useState(false);

  const addWidget = (type: WidgetType) => {
    const w: WidgetConfig = {
      id:   newId(),
      type,
      title: `新${type}图`,
      height: 240,
    };
    setWidgets(prev => [...prev, w]);
    setSelected(w.id);
  };

  const updateWidget = (updated: WidgetConfig) =>
    setWidgets(prev => prev.map(w => w.id === updated.id ? updated : w));

  const removeWidget = (id: string) => {
    setWidgets(prev => prev.filter(w => w.id !== id));
    if (selected === id) setSelected(null);
  };

  const selectedWidget = widgets.find(w => w.id === selected) ?? null;

  const save = async () => {
    if (!name.trim()) return;
    setSaving(true);
    await onSave(name, widgets);
    setSaving(false);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-gray-900 border-b border-gray-800">
        <input
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white w-56 focus:outline-none focus:border-blue-500"
          placeholder="报表名称"
          value={name}
          onChange={e => setName(e.target.value)}
        />
        <span className="text-gray-600 text-xs">{widgets.length} 个组件</span>
        <div className="flex-1" />
        <button
          onClick={() => setWidgets([])}
          className="text-xs text-gray-500 hover:text-red-400"
        >
          清空
        </button>
        <button
          onClick={save}
          disabled={!name.trim() || saving}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded"
        >
          {saving ? "保存中…" : "保存报表"}
        </button>
      </div>

      {/* Three-panel layout */}
      <div className="flex flex-1 overflow-hidden">
        <WidgetPalette onAdd={addWidget} />
        <CanvasArea
          widgets={widgets}
          selected={selected}
          onSelect={setSelected}
          onRemove={removeWidget}
          onDrop={addWidget}
        />
        <PropertyPanel
          widget={selectedWidget}
          onChange={updateWidget}
        />
      </div>
    </div>
  );
}
