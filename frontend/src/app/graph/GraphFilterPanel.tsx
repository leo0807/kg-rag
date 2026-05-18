"use client";

import {
  EDGE_TYPES,
  type EdgeFilter,
  NODE_COLOR,
  NODE_SHORT,
  NODE_TYPES,
  type NodeFilter,
} from "./constants";

interface Props {
  nodeFilter: NodeFilter;
  setNodeFilter: (v: NodeFilter) => void;
  edgeFilter: EdgeFilter;
  setEdgeFilter: (v: EdgeFilter) => void;
  showTables: boolean;
  onToggleTables: () => void;
}

export function GraphFilterPanel({
  nodeFilter,
  setNodeFilter,
  edgeFilter,
  setEdgeFilter,
  showTables,
  onToggleTables,
}: Props) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-1">
      <div className="flex flex-wrap items-center gap-1">
        {NODE_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => setNodeFilter(type)}
            title={type}
            className={`flex items-center gap-1 px-2.5 h-8 rounded text-xs font-medium transition-colors whitespace-nowrap ${
              nodeFilter === type
                ? "bg-indigo-600 text-white"
                : "text-gray-400 hover:text-gray-100 hover:bg-gray-800"
            }`}
          >
            {type !== "全部" && (
              <span
                className="w-1.5 h-1.5 rounded-full shrink-0"
                style={{ backgroundColor: NODE_COLOR[type] }}
              />
            )}
            {NODE_SHORT[type]}
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={onToggleTables}
        title={showTables ? "隐藏表格节点" : "显示表格节点（默认关闭）"}
        className={`flex items-center gap-1 px-2.5 h-8 rounded text-xs font-medium transition-colors ${
          showTables
            ? "bg-green-600 text-white"
            : "text-gray-500 hover:text-gray-100 hover:bg-gray-800 border border-dashed border-gray-700"
        }`}
      >
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ backgroundColor: "#22c55e" }}
        />
        表格
      </button>

      <div className="hidden h-5 w-px shrink-0 bg-gray-700 mx-0.5 sm:block" />

      <select
        value={edgeFilter}
        onChange={(e) => setEdgeFilter(e.target.value as EdgeFilter)}
        className="h-8 w-full rounded border border-gray-700 bg-gray-800 px-2 text-xs text-gray-300 outline-none focus:border-indigo-500 sm:max-w-[138px]"
      >
        {EDGE_TYPES.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
    </div>
  );
}
