"use client";

import { GitBranch, Plus, Trash2 } from "lucide-react";
import { usePipeline } from "./usePipeline";
import { NodePanel } from "./NodePanel";
import { NodeConfig } from "./NodeConfig";
import { PipelineToolbar } from "./PipelineToolbar";
import { PipelineCanvas } from "./PipelineCanvas";

export default function PipelinePage() {
  const {
    schema, configs, activeConfigId, nodes, edges,
    selectedNode,
    saving, validating, validateResult, error,
    setActiveConfigId, loadConfig,
    onNodesChange, onEdgesChange, onConnect,
    addNode, updateNodeParam, deleteSelectedNode,
    setSelectedNodeId, applyPreset, validate, save, setDefault, deleteConfig, newConfig,
    clearCanvas, copySelected, pasteClipboard, cutSelected,
  } = usePipeline();

  function handleAddNodeAtCenter(nodeType: string) {
    addNode(nodeType, { x: 250 + Math.random() * 100, y: 150 + Math.random() * 80 });
  }

  function handleAddNodeAt(nodeType: string, position: { x: number; y: number }) {
    addNode(nodeType, position);
  }

  return (
    <div className="flex h-full flex-col bg-gray-950">
      {/* Page header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-indigo-500/10 p-2">
            <GitBranch size={18} className="text-indigo-400" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white">检索链路配置器</h1>
            <p className="text-xs text-gray-500">可视化编排检索→处理→生成节点，设置为默认后将用于智能问答</p>
          </div>
        </div>
        {error && (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-300">
            {error}
          </div>
        )}
      </div>

      {/* Config tabs */}
      <div className="flex items-center gap-1 border-b border-gray-800 bg-gray-950 px-4 py-2 overflow-x-auto">
        {configs.map((cfg) => (
          <div key={cfg.id} className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => { setActiveConfigId(cfg.id); loadConfig(cfg); }}
              className={`flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium transition-colors ${
                activeConfigId === cfg.id
                  ? "bg-indigo-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}
            >
              {cfg.name}
              {cfg.is_default && (
                <span className="rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-[9px] text-emerald-400">默认</span>
              )}
            </button>
            {activeConfigId === cfg.id && !cfg.is_default && (
              <button
                type="button"
                onClick={() => setDefault(cfg.id)}
                className="rounded-lg px-2 py-1 text-[10px] text-gray-500 hover:text-emerald-400"
                title="设为默认"
              >
                设默认
              </button>
            )}
            {configs.length > 1 && activeConfigId === cfg.id && (
              <button
                type="button"
                onClick={() => deleteConfig(cfg.id)}
                className="rounded-lg p-1 text-gray-600 hover:text-red-400"
                title="删除配置"
              >
                <Trash2 size={11} />
              </button>
            )}
          </div>
        ))}
        <button
          type="button"
          onClick={newConfig}
          className="ml-1 flex items-center gap-1 rounded-xl px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-800 hover:text-gray-300"
        >
          <Plus size={12} /> 新建
        </button>
      </div>

      {/* Toolbar */}
      <PipelineToolbar
        saving={saving}
        validating={validating}
        validateResult={validateResult}
        onValidate={validate}
        onSave={save}
        onPreset={applyPreset}
        onClear={clearCanvas}
      />

      {/* Main editor area */}
      <div className="flex flex-1 overflow-hidden">
        <NodePanel schema={schema} onAddNode={handleAddNodeAtCenter} />
        <PipelineCanvas
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={setSelectedNodeId}
          onAddNode={handleAddNodeAt}
          onPaneClick={() => setSelectedNodeId(null)}
          onCopy={copySelected}
          onPaste={pasteClipboard}
          onCut={cutSelected}
        />
        <NodeConfig
          node={selectedNode}
          schema={schema}
          onUpdateParam={updateNodeParam}
          onDelete={deleteSelectedNode}
        />
      </div>
    </div>
  );
}
