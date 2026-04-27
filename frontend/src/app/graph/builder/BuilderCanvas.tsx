"use client";

import {
    ReactFlow, Background, Controls, MiniMap, Panel,
} from '@xyflow/react';
import {
    AlertCircle, BookOpen, CheckCircle2, Code, Copy, Database,
    Play, Trash2, X, HelpCircle,
} from 'lucide-react';
import { EXAMPLES } from './useBuilder';

interface Props {
    nodes: any; edges: any;
    onNodesChange: any; onEdgesChange: any;
    onConnect: any; onEdgeClick: any;
    nodeTypes: any;
    cypher: string; results: any;
    loading: boolean; error: string | null;
    copied: boolean; showTutorial: boolean;
    setError: (e: string | null) => void;
    setShowTutorial: (v: boolean) => void;
    onRun: () => void; onClear: () => void; onCopy: () => void;
    onLoadExample: (ex: any) => void;
}

export function BuilderCanvas({
    nodes, edges, onNodesChange, onEdgesChange, onConnect, onEdgeClick, nodeTypes,
    cypher, results, loading, error, copied, showTutorial,
    setError, setShowTutorial, onRun, onClear, onCopy, onLoadExample,
}: Props) {
    return (
        <div className="flex-1 relative flex flex-col">
            <div className="flex-1 relative">
                <ReactFlow
                    nodes={nodes} edges={edges}
                    onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
                    onConnect={onConnect} onEdgeClick={onEdgeClick}
                    nodeTypes={nodeTypes} colorMode="dark" fitView
                >
                    <Background color="#111827" gap={20} size={1} />
                    <Controls className="!bg-gray-900 !border-gray-800 !fill-gray-400" />
                    <MiniMap nodeStrokeColor="#4f46e5" nodeColor="#1e1b4b" maskColor="rgba(0,0,0,0.7)"
                        style={{ background: '#030712', borderRadius: '12px', border: '1px solid #1f2937' }} />

                    <Panel position="top-right" className="flex gap-2">
                        <div className="bg-gray-900/80 backdrop-blur border border-gray-800 p-1 rounded-xl flex gap-1 shadow-2xl">
                            <button onClick={() => setShowTutorial(true)}
                                className="flex items-center gap-2 px-3 py-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg text-sm transition-all">
                                <HelpCircle size={16} />使用指南
                            </button>
                            <div className="w-px h-4 bg-gray-800 self-center mx-1" />
                            <button onClick={onRun} disabled={!cypher || loading}
                                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-bold transition-all shadow-lg shadow-indigo-500/20">
                                <Play size={14} fill="currentColor" />
                                {loading ? '执行中...' : '运行查询'}
                            </button>
                            <button onClick={onClear} className="p-2 text-gray-500 hover:text-red-400 transition-colors" title="清空画布">
                                <Trash2 size={18} />
                            </button>
                        </div>
                    </Panel>

                    {showTutorial && (
                        <Panel position="center" className="w-[500px] pointer-events-auto">
                            <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.5)] p-6">
                                <div className="flex items-center justify-between mb-6">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-indigo-500/20 rounded-lg"><BookOpen className="text-indigo-400" size={20} /></div>
                                        <h2 className="text-lg font-bold text-white">Cypher 构造器快速上手</h2>
                                    </div>
                                    <button onClick={() => setShowTutorial(false)} className="text-gray-500 hover:text-white"><X size={20} /></button>
                                </div>
                                <div className="space-y-3">
                                    {EXAMPLES.map((ex, i) => (
                                        <div key={i} onClick={() => onLoadExample(ex)}
                                            className="group p-4 bg-gray-800/40 border border-gray-700 rounded-xl cursor-pointer hover:border-indigo-500 hover:bg-indigo-500/5 transition-all">
                                            <div className="flex items-center justify-between mb-1">
                                                <h3 className="text-sm font-bold text-gray-200 group-hover:text-indigo-300">{ex.title}</h3>
                                                <span className="text-[10px] bg-gray-700 px-1.5 py-0.5 rounded text-gray-500 group-hover:bg-indigo-500/20 group-hover:text-indigo-400 transition-colors">加载示例</span>
                                            </div>
                                            <p className="text-xs text-gray-500 leading-normal">{ex.desc}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </Panel>
                    )}

                    {error && (
                        <Panel position="top-center" className="max-w-md">
                            <div className="bg-red-950/40 border border-red-500/50 backdrop-blur-md p-3 rounded-xl flex gap-3 shadow-2xl">
                                <AlertCircle className="text-red-400 shrink-0" size={18} />
                                <div className="flex-1 min-w-0">
                                    <div className="text-xs font-bold text-red-300 uppercase mb-1">查询错误</div>
                                    <div className="text-[11px] text-red-200/80 font-mono break-all">{error}</div>
                                </div>
                                <button onClick={() => setError(null)} className="text-red-400 hover:text-white transition-colors"><X size={14} /></button>
                            </div>
                        </Panel>
                    )}
                </ReactFlow>
            </div>

            {/* Bottom panel */}
            <div className="h-72 border-t border-gray-800 bg-[#030712] flex shadow-[0_-10px_30px_rgba(0,0,0,0.5)] z-10">
                <div className="w-2/5 border-r border-gray-900 p-5 flex flex-col">
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                            <Code size={14} className="text-indigo-500" /> Cypher 代码预览
                        </div>
                        <button onClick={onCopy}
                            className={`flex items-center gap-1.5 text-[10px] font-bold transition-colors ${copied ? 'text-emerald-400' : 'text-indigo-400 hover:text-indigo-300'}`}>
                            {copied ? <CheckCircle2 size={12} /> : <Copy size={12} />} {copied ? '已复制' : '复制代码'}
                        </button>
                    </div>
                    <div className="flex-1 bg-gray-900/30 rounded-xl p-4 font-mono text-sm overflow-auto border border-gray-800/50">
                        {cypher
                            ? <code className="text-indigo-300 block whitespace-pre leading-relaxed">{cypher}</code>
                            : <div className="h-full flex items-center justify-center opacity-20 italic text-xs">// 从左侧添加实体并建立连线生成查询...</div>}
                    </div>
                </div>
                <div className="w-3/5 p-5 flex flex-col">
                    <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-3">
                        <Database size={14} className="text-emerald-500" /> 执行结果集
                        {results?.nodes && <span className="ml-2 px-1.5 py-0.5 bg-emerald-500/10 text-emerald-500 rounded text-[9px]">{results.nodes.length} 节点 / {results.edges.length} 关系</span>}
                    </div>
                    <div className="flex-1 bg-gray-900/30 rounded-xl p-4 overflow-auto border border-gray-800/50">
                        {results ? (
                            <div className="grid grid-cols-1 gap-2">
                                {results.nodes.map((n: any, i: number) => (
                                    <div key={i} className="p-3 bg-gray-800/40 border border-gray-700 rounded-lg text-[11px]">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="px-1.5 py-0.5 bg-indigo-500/20 text-indigo-400 rounded font-bold uppercase text-[9px]">{n.type}</span>
                                            <span className="text-gray-600 font-mono text-[9px]">{n.id}</span>
                                        </div>
                                        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                                            {Object.entries(n.properties || {}).slice(0, 6).map(([k, v]: any) => (
                                                <div key={k} className="flex gap-2 truncate">
                                                    <span className="text-gray-500 shrink-0">{k}:</span>
                                                    <span className="text-gray-300 truncate" title={String(v)}>{String(v)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="h-full flex flex-col items-center justify-center opacity-20">
                                <Database size={40} className="mb-2" /><p className="text-xs italic">等待查询执行结果...</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
