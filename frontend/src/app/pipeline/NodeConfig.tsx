"use client";

import { Trash2 } from "lucide-react";
import type { NodeParamDef, NodeTypeDef, ParamValue, PipelineNode } from "./types";

interface Props {
  node: PipelineNode | null;
  schema: Record<string, NodeTypeDef>;
  onUpdateParam: (nodeId: string, key: string, value: ParamValue) => void;
  onDelete: () => void;
}

interface ParamProps {
  nodeId: string;
  paramKey: string;
  paramDef: NodeParamDef;
  value: ParamValue;
  onChange: (key: string, value: ParamValue) => void;
}

function ParamControl({ nodeId: _, paramKey, paramDef, value, onChange }: ParamProps) {
  const { type, min, max, options } = paramDef;

  if (type === "bool") {
    return (
      <label className="flex cursor-pointer items-center gap-2">
        <div className="relative">
          <input
            type="checkbox"
            className="sr-only"
            checked={Boolean(value)}
            onChange={(e) => onChange(paramKey, e.target.checked)}
          />
          <div className={`h-4 w-8 rounded-full transition-colors ${Boolean(value) ? "bg-indigo-500" : "bg-gray-700"}`} />
          <div className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-transform ${Boolean(value) ? "translate-x-4" : "translate-x-0.5"}`} />
        </div>
        <span className="text-xs text-gray-400">{Boolean(value) ? "开" : "关"}</span>
      </label>
    );
  }

  if (type === "select") {
    return (
      <select
        value={String(value)}
        onChange={(e) => onChange(paramKey, e.target.value)}
        className="w-full rounded-lg border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-white outline-none focus:border-indigo-500"
      >
        {(options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }

  if (type === "multiselect") {
    const selected = Array.isArray(value) ? value : [];
    return (
      <div className="flex flex-wrap gap-1">
        {(options ?? []).map((o) => {
          const checked = selected.includes(o);
          return (
            <button
              key={o}
              type="button"
              onClick={() => onChange(paramKey, checked ? selected.filter((s) => s !== o) : [...selected, o])}
              className={`rounded px-1.5 py-0.5 text-[10px] border transition-colors ${checked ? "border-indigo-500 bg-indigo-500/20 text-indigo-300" : "border-gray-700 bg-gray-800 text-gray-500 hover:text-gray-300"}`}
            >
              {o}
            </button>
          );
        })}
      </div>
    );
  }

  if (type === "text") {
    return (
      <input
        type="text"
        value={String(value)}
        onChange={(e) => onChange(paramKey, e.target.value)}
        className="w-full rounded-lg border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-white outline-none focus:border-indigo-500"
      />
    );
  }

  if (type === "textarea") {
    return (
      <textarea
        value={String(value)}
        rows={3}
        onChange={(e) => onChange(paramKey, e.target.value)}
        className="w-full resize-none rounded-lg border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-white outline-none focus:border-indigo-500"
      />
    );
  }

  // int / float
  const isFloat = type === "float";
  const hasRange = min !== undefined && max !== undefined;
  return (
    <>
      <div className="flex justify-end text-xs font-mono text-white">
        {isFloat ? Number(value).toFixed(2) : value}
      </div>
      {hasRange ? (
        <input
          type="range" min={min} max={max} step={isFloat ? 0.05 : 1} value={Number(value)}
          onChange={(e) => onChange(paramKey, isFloat ? parseFloat(e.target.value) : parseInt(e.target.value))}
          className="h-1.5 w-full cursor-pointer accent-indigo-500"
        />
      ) : (
        <input
          type="number" step={isFloat ? 0.1 : 1} value={Number(value)}
          onChange={(e) => onChange(paramKey, isFloat ? parseFloat(e.target.value) : parseInt(e.target.value))}
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-white outline-none focus:border-indigo-500"
        />
      )}
    </>
  );
}

export function NodeConfig({ node, schema, onUpdateParam, onDelete }: Props) {
  if (!node) {
    return (
      <div className="flex h-full w-56 shrink-0 flex-col items-center justify-center gap-2 border-l border-gray-800 bg-gray-950 p-4">
        <div className="text-xs text-gray-600">点击节点编辑参数</div>
      </div>
    );
  }

  const def = schema[node.data.nodeType];
  if (!def) return null;

  return (
    <div className="flex h-full w-56 shrink-0 flex-col gap-4 overflow-y-auto border-l border-gray-800 bg-gray-950 p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-white">{node.data.label}</div>
          <div className="text-[10px] text-gray-500">{node.id}</div>
        </div>
        <button type="button" onClick={onDelete}
          className="rounded-lg p-1.5 text-gray-500 hover:bg-red-500/10 hover:text-red-400">
          <Trash2 size={14} />
        </button>
      </div>

      <div className="flex flex-col gap-4">
        {Object.entries(def.params).map(([key, paramDef]) => {
          const val = node.data.params[key] ?? paramDef.default;
          return (
            <div key={key} className="flex flex-col gap-1.5">
              <div className="text-xs text-gray-400">{paramDef.label}</div>
              <ParamControl
                nodeId={node.id}
                paramKey={key}
                paramDef={paramDef}
                value={val}
                onChange={(k, v) => onUpdateParam(node.id, k, v)}
              />
            </div>
          );
        })}
      </div>

      <div className="mt-auto">
        <div className="rounded-xl border border-gray-800 p-2 text-[10px] text-gray-600">
          <div className="mb-1 font-medium text-gray-500">端口</div>
          <div>输入：{def.inputs.join(", ")}</div>
          <div>输出：{def.outputs.join(", ")}</div>
        </div>
      </div>
    </div>
  );
}
