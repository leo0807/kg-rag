"use client";

import { Handle, NodeProps, Position, ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Database, Info } from 'lucide-react';
import { useBuilder } from './useBuilder';
import { BuilderCanvas } from './BuilderCanvas';

const NODE_COLORS: Record<string, string> = {
    Document: 'border-amber-500 bg-amber-950/40 text-amber-200',
    Section:  'border-indigo-500 bg-indigo-950/40 text-indigo-200',
    Tool:     'border-emerald-500 bg-emerald-950/40 text-emerald-200',
    Material: 'border-blue-500 bg-blue-950/40 text-blue-200',
    Process:  'border-purple-500 bg-purple-950/40 text-purple-200',
    Constraint: 'border-pink-500 bg-pink-950/40 text-pink-200',
};

const SchemaNode = ({ data, selected }: NodeProps) => {
    const label = data.label as string;
    const colorClass = NODE_COLORS[label] || 'border-gray-500 bg-gray-900 text-gray-300';
    return (
        <div className={`px-4 py-2 rounded-lg border-2 shadow-xl min-w-[120px] transition-all ${colorClass} ${selected ? 'ring-2 ring-white scale-105' : ''}`}>
            <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-gray-400" />
            <div className="text-[10px] opacity-50 font-bold uppercase mb-1">Entity</div>
            <div className="text-sm font-bold truncate">{label}</div>
            <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-gray-400" />
        </div>
    );
};

const nodeTypes = { schemaNode: SchemaNode };

function BuilderInternal() {
    const {
        nodes, edges, onNodesChange, onEdgesChange, onConnect, onEdgeClick,
        schema, cypher, results, loading, error, setError,
        copied, showTutorial, setShowTutorial,
        addNode, loadExample, runQuery, copyToClipboard, clearCanvas,
    } = useBuilder();

    return (
        <div className="flex h-screen bg-[#030712] text-gray-200 overflow-hidden font-sans">
            {/* Sidebar */}
            <div className="w-64 border-r border-gray-800 bg-gray-950/50 backdrop-blur-xl p-5 flex flex-col gap-6 z-20">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-indigo-600/20 rounded-lg"><Database className="text-indigo-500" size={20} /></div>
                    <div>
                        <h1 className="font-bold text-white tracking-tight">Cypher Builder</h1>
                        <p className="text-[10px] text-gray-500 font-medium">可视化图查询引擎</p>
                    </div>
                </div>
                <div className="flex-1 overflow-y-auto pr-2 space-y-6 scrollbar-hide">
                    <div>
                        <label className="text-[10px] text-gray-500 font-bold uppercase tracking-[0.1em] mb-3 block">可用实体标签</label>
                        <div className="flex flex-col gap-2">
                            {schema.labels.map(l => (
                                <button key={l} onClick={() => addNode(l)}
                                    className="px-3 py-2.5 bg-gray-900/50 border border-gray-800 rounded-xl text-xs text-left hover:border-indigo-500/50 hover:bg-indigo-500/5 transition-all flex items-center justify-between group">
                                    <span className="font-medium">{l}</span>
                                    <span className="text-[8px] opacity-0 group-hover:opacity-100 bg-indigo-500/20 px-1.5 py-0.5 rounded text-indigo-400 transition-opacity">点击添加</span>
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
                <div className="pt-4 border-t border-gray-800">
                    <div className="p-3 bg-indigo-950/20 border border-indigo-500/20 rounded-xl flex gap-3">
                        <Info size={16} className="text-indigo-400 shrink-0 mt-0.5" />
                        <p className="text-[10px] text-indigo-300/70 leading-relaxed">通过连接节点构建逻辑链路，系统将实时生成 Neo4j 标准 Cypher 查询语句。</p>
                    </div>
                </div>
            </div>

            <BuilderCanvas
                nodes={nodes} edges={edges}
                onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
                onConnect={onConnect} onEdgeClick={onEdgeClick}
                nodeTypes={nodeTypes}
                cypher={cypher} results={results}
                loading={loading} error={error} setError={setError}
                copied={copied} showTutorial={showTutorial} setShowTutorial={setShowTutorial}
                onRun={runQuery} onClear={clearCanvas} onCopy={copyToClipboard}
                onLoadExample={loadExample}
            />
        </div>
    );
}

export default function CypherBuilderPage() {
    return (
        <ReactFlowProvider>
            <BuilderInternal />
        </ReactFlowProvider>
    );
}
