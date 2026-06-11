"use client";
import { useState } from "react";

export type GraphFilter = {
  nodeTypes: string[];
  relTypes: string[];
  minStrength: number;
  maxDepth: number;
  docFilter: string;
};

const DEFAULT_FILTERS: GraphFilter = {
  nodeTypes: [],
  relTypes: [],
  minStrength: 0,
  maxDepth: 3,
  docFilter: "",
};

type Props = {
  nodeTypeOptions: string[];
  relTypeOptions:  string[];
  filters: GraphFilter;
  onChange: (f: GraphFilter) => void;
};

const CHIP = (active: boolean) =>
  `text-xs px-2 py-1 rounded cursor-pointer border transition-colors ${
    active ? "bg-blue-600 border-blue-600 text-white" : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500"
  }`;

export function GraphFilters({ nodeTypeOptions, relTypeOptions, filters, onChange }: Props) {
  const [open, setOpen] = useState(true);

  const toggle = (key: "nodeTypes" | "relTypes", val: string) => {
    const cur = filters[key];
    const next = cur.includes(val) ? cur.filter(v => v !== val) : [...cur, val];
    onChange({ ...filters, [key]: next });
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm text-white hover:bg-gray-800"
      >
        <span className="font-medium">图谱过滤器</span>
        <span className="text-gray-500 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4">
          {/* Node type filter */}
          {nodeTypeOptions.length > 0 && (
            <div>
              <p className="text-gray-400 text-xs mb-2">节点类型</p>
              <div className="flex flex-wrap gap-1.5">
                {nodeTypeOptions.map(t => (
                  <span
                    key={t}
                    className={CHIP(filters.nodeTypes.length === 0 || filters.nodeTypes.includes(t))}
                    onClick={() => toggle("nodeTypes", t)}
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Relationship type filter */}
          {relTypeOptions.length > 0 && (
            <div>
              <p className="text-gray-400 text-xs mb-2">关系类型</p>
              <div className="flex flex-wrap gap-1.5">
                {relTypeOptions.map(t => (
                  <span
                    key={t}
                    className={CHIP(filters.relTypes.length === 0 || filters.relTypes.includes(t))}
                    onClick={() => toggle("relTypes", t)}
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Strength slider */}
          <div>
            <p className="text-gray-400 text-xs mb-2">最低关系强度: {filters.minStrength}</p>
            <input
              type="range" min={0} max={10} step={1}
              value={filters.minStrength}
              onChange={e => onChange({ ...filters, minStrength: Number(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </div>

          {/* Depth */}
          <div>
            <p className="text-gray-400 text-xs mb-2">展开深度: {filters.maxDepth}</p>
            <input
              type="range" min={1} max={6} step={1}
              value={filters.maxDepth}
              onChange={e => onChange({ ...filters, maxDepth: Number(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </div>

          {/* Doc filter */}
          <div>
            <p className="text-gray-400 text-xs mb-1">文档过滤</p>
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
              placeholder="文档名称关键词"
              value={filters.docFilter}
              onChange={e => onChange({ ...filters, docFilter: e.target.value })}
            />
          </div>

          {/* Reset */}
          <button
            onClick={() => onChange(DEFAULT_FILTERS)}
            className="text-xs text-gray-500 hover:text-white"
          >
            重置过滤器
          </button>
        </div>
      )}
    </div>
  );
}
