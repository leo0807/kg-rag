"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import type { PipelineNodeData } from "./types";

function PipelineNodeComponent({ data, selected }: NodeProps<PipelineNodeData>) {
  const borderColor = data.category === "retrieval"
    ? "border-blue-500/60"
    : data.category === "processing"
    ? "border-orange-500/60"
    : "border-emerald-500/60";

  const headerBg = data.category === "retrieval"
    ? "bg-blue-600/30"
    : data.category === "processing"
    ? "bg-orange-600/30"
    : "bg-emerald-600/30";

  return (
    <div
      className={`min-w-[140px] rounded-xl border bg-gray-900 shadow-xl transition-all ${borderColor} ${selected ? "ring-2 ring-white/30" : ""}`}
    >
      {/* Input handles */}
      {data.inputs.map((port, i) => (
        <Handle
          key={`in-${port}`}
          type="target"
          position={Position.Left}
          id={port}
          style={{ top: `${((i + 1) / (data.inputs.length + 1)) * 100}%` }}
          className="!h-3 !w-3 !border-2 !border-gray-600 !bg-gray-800"
        />
      ))}

      {/* Header */}
      <div className={`rounded-t-xl px-3 py-2 ${headerBg}`}>
        <div className="text-xs font-semibold text-white">{data.label}</div>
      </div>

      {/* Params preview */}
      <div className="px-3 py-2">
        {Object.entries(data.params).slice(0, 2).map(([key, val]) => (
          <div key={key} className="flex justify-between text-[10px] text-gray-400">
            <span>{key}</span>
            <span className="text-gray-300">{String(val)}</span>
          </div>
        ))}
      </div>

      {/* Output handles */}
      {data.outputs.map((port, i) => (
        <Handle
          key={`out-${port}`}
          type="source"
          position={Position.Right}
          id={port}
          style={{ top: `${((i + 1) / (data.outputs.length + 1)) * 100}%` }}
          className="!h-3 !w-3 !border-2 !border-gray-600 !bg-gray-800"
        />
      ))}
    </div>
  );
}

export const PipelineNodeRenderer = memo(PipelineNodeComponent);

export const nodeTypes = {
  pipelineNode: PipelineNodeRenderer,
};
