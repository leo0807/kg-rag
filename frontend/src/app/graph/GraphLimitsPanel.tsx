"use client";

import type { Dispatch, SetStateAction } from "react";
import type { Limits } from "./constants";

interface Props {
  limits: Limits;
  setLimits: Dispatch<SetStateAction<Limits>>;
}

export function GraphLimitsPanel({ limits, setLimits }: Props) {
  return (
    <div className="absolute top-3 left-3 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 space-y-3 w-56 z-10 shadow-xl">
      <div className="text-xs text-gray-400 font-medium">节点数量限制</div>
      {(
        [
          { key: "doc", label: "Document", min: 10, max: 500 },
          { key: "sec", label: "Section", min: 50, max: 2000 },
          { key: "entity", label: "Entity", min: 20, max: 1000 },
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
            onChange={(e) =>
              setLimits((prev) => ({ ...prev, [key]: Number(e.target.value) }))
            }
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
