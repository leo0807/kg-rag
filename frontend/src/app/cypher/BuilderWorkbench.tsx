"use client";

import {
  Handle,
  type NodeProps,
  Position,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Database, Info } from "lucide-react";
import { BuilderCanvas } from "../graph/builder/BuilderCanvas";
import { useBuilder } from "../graph/builder/useBuilder";

const NODE_COLORS: Record<string, string> = {
  Document: "border-amber-500 bg-amber-950/40 text-amber-200",
  Section: "border-indigo-500 bg-indigo-950/40 text-indigo-200",
  Tool: "border-emerald-500 bg-emerald-950/40 text-emerald-200",
  Material: "border-blue-500 bg-blue-950/40 text-blue-200",
  Process: "border-purple-500 bg-purple-950/40 text-purple-200",
  Constraint: "border-pink-500 bg-pink-950/40 text-pink-200",
};

const SchemaNode = ({ data, selected }: NodeProps) => {
  const label = data.label as string;
  const colorClass =
    NODE_COLORS[label] || "border-gray-500 bg-gray-900 text-gray-300";
  return (
    <div
      className={`min-w-[120px] rounded-lg border-2 px-4 py-2 shadow-xl transition-all ${colorClass} ${selected ? "scale-105 ring-2 ring-white" : ""}`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="h-2 w-2 !bg-gray-400"
      />
      <div className="mb-1 text-[10px] font-bold uppercase opacity-50">
        Entity
      </div>
      <div className="truncate text-sm font-bold">{label}</div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="h-2 w-2 !bg-gray-400"
      />
    </div>
  );
};

const nodeTypes = { schemaNode: SchemaNode };

function BuilderInternal() {
  const {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onEdgeClick,
    schema,
    cypher,
    results,
    loading,
    error,
    setError,
    copied,
    showTutorial,
    setShowTutorial,
    addNode,
    loadExample,
    runQuery,
    copyToClipboard,
    clearCanvas,
  } = useBuilder();

  return (
    <div className="flex h-full min-h-0 overflow-hidden bg-[#030712] font-sans text-gray-200">
      <div className="z-20 flex w-64 flex-col gap-6 border-r border-gray-800 bg-gray-950/50 p-5 backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-indigo-600/20 p-2">
            <Database className="text-indigo-500" size={20} />
          </div>
          <div>
            <h1 className="font-bold tracking-tight text-white">
              Cypher Builder
            </h1>
            <p className="text-[10px] font-medium text-gray-500">
              可视化图查询引擎
            </p>
          </div>
        </div>

        <div className="scrollbar-hide flex-1 space-y-6 overflow-y-auto pr-2">
          <div>
            <div className="mb-3 block text-[10px] font-bold uppercase tracking-[0.1em] text-gray-500">
              可用实体标签
            </div>
            <div className="flex flex-col gap-2">
              {schema.labels.map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => addNode(l)}
                  className="group flex items-center justify-between rounded-xl border border-gray-800 bg-gray-900/50 px-3 py-2.5 text-left text-xs transition-all hover:border-indigo-500/50 hover:bg-indigo-500/5"
                >
                  <span className="font-medium">{l}</span>
                  <span className="rounded bg-indigo-500/20 px-1.5 py-0.5 text-[8px] text-indigo-400 opacity-0 transition-opacity group-hover:opacity-100">
                    点击添加
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-gray-800 pt-4">
          <div className="flex gap-3 rounded-xl border border-indigo-500/20 bg-indigo-950/20 p-3">
            <Info className="mt-0.5 shrink-0 text-indigo-400" size={16} />
            <p className="text-[10px] leading-relaxed text-indigo-300/70">
              通过连接节点构建逻辑链路，系统将实时生成 Neo4j 标准 Cypher
              查询语句。
            </p>
          </div>
        </div>
      </div>

      <BuilderCanvas
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onEdgeClick={onEdgeClick}
        nodeTypes={nodeTypes}
        cypher={cypher}
        results={results}
        loading={loading}
        error={error}
        setError={setError}
        copied={copied}
        showTutorial={showTutorial}
        setShowTutorial={setShowTutorial}
        onRun={runQuery}
        onClear={clearCanvas}
        onCopy={copyToClipboard}
        onLoadExample={loadExample}
      />
    </div>
  );
}

export function CypherBuilderWorkbench() {
  return (
    <ReactFlowProvider>
      <BuilderInternal />
    </ReactFlowProvider>
  );
}
