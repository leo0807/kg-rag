"use client";

import type { Dispatch, SetStateAction } from "react";
import { GRAPH_NODE_LIMITS, type Limits } from "./constants";

interface Props {
  limits: Limits;
  setLimits: Dispatch<SetStateAction<Limits>>;
}

export function GraphLimitsPanel({ limits, setLimits }: Props) {
  function handleLimitChange(key: keyof Limits, value: number) {
    if (
      key === "sec" &&
      value > 1000 &&
      limits.sec <= 1000 &&
      !window.confirm(
        "加载超过1000个章节节点可能影响浏览器性能，建议使用文档筛选器缩小范围，确认继续？",
      )
    ) {
      return;
    }
    setLimits((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-3 space-y-3 shadow-xl">
      <div className="text-xs text-gray-400 font-medium">节点数量限制</div>
      {(
        [
          {
            key: "doc",
            label: "Document",
            min: 10,
            max: GRAPH_NODE_LIMITS.doc.max,
          },
          {
            key: "sec",
            label: "Section",
            min: 50,
            max: GRAPH_NODE_LIMITS.sec.max,
          },
          {
            key: "entity",
            label: "Entity",
            min: 20,
            max: GRAPH_NODE_LIMITS.entity.max,
          },
        ] as { key: keyof Limits; label: string; min: number; max: number }[]
      ).map(({ key, label, min, max }) => (
        <div key={key} className="flex items-center gap-2">
          <span className="text-xs text-gray-400 w-16">{label}</span>
          <input
            type="range"
            min={min}
            max={max}
            step={10}
            value={limits[key] as number}
            onChange={(e) => handleLimitChange(key, Number(e.target.value))}
            className="flex-1 h-1 accent-indigo-500"
          />
          <span className="text-xs text-gray-500 w-8 text-right">
            {limits[key] as number}
          </span>
        </div>
      ))}
    </div>
  );
}
