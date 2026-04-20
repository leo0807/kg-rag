"use client";

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  addEdge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  Panel,
  MarkerType,
  Handle,
  Position,
  NodeProps,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { 
  Play, Save, Trash2, Code, Database, Info, X, 
  AlertCircle, Copy, CheckCircle2, HelpCircle, BookOpen 
} from 'lucide-react';

// --- 自定义节点组件 ---
const SchemaNode = ({ data, selected }: NodeProps) => {
  const label = data.label as string;
  const colors: Record<string, string> = {
    Document: 'border-amber-500 bg-amber-950/40 text-amber-200',
    Section: 'border-indigo-500 bg-indigo-950/40 text-indigo-200',
    Tool: 'border-emerald-500 bg-emerald-950/40 text-emerald-200',
    Material: 'border-blue-500 bg-blue-950/40 text-blue-200',
    Process: 'border-purple-500 bg-purple-950/40 text-purple-200',
    Constraint: 'border-pink-500 bg-pink-950/40 text-pink-200',
  };

  const colorClass = colors[label] || 'border-gray-500 bg-gray-900 text-gray-300';

  return (
    <div className={`px-4 py-2 rounded-lg border-2 shadow-xl min-w-[120px] transition-all
                    ${colorClass} ${selected ? 'ring-2 ring-white scale-105' : ''}`}>
      <Handle type="target" position={Position.Top} className="w-2 h-2 !bg-gray-400" />
      <div className="text-[10px] opacity-50 font-bold uppercase mb-1">Entity</div>
      <div className="text-sm font-bold truncate">{label}</div>
      <Handle type="source" position={Position.Bottom} className="w-2 h-2 !bg-gray-400" />
    </div>
  );
};

const nodeTypes = {
  schemaNode: SchemaNode,
};

// --- 内部页面组件 (为了使用 useReactFlow) ---
function BuilderInternal() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [schema, setSchema] = useState<{ labels: string[], relationship_types: string[] }>({ labels: [], relationship_types: [] });
  const [cypher, setCypher] = useState('');
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);
  
  const { fitView } = useReactFlow();

  // 预设示例数据
  const examples = [
    {
      title: "文档结构检索",
      desc: "查找规范下属的所有章节，了解文档大纲。",
      nodes: [
        { id: 'ex1_n1', type: 'schemaNode', position: { x: 100, y: 100 }, data: { label: 'Document' } },
        { id: 'ex1_n2', type: 'schemaNode', position: { x: 100, y: 300 }, data: { label: 'Section' } },
      ],
      edges: [
        { id: 'ex1_e1', source: 'ex1_n1', target: 'ex1_n2', label: 'HAS_SECTION', type: 'smoothstep', markerEnd: { type: MarkerType.ArrowClosed } }
      ]
    },
    {
      title: "工艺资源配套",
      desc: "查询特定工序需要哪些工具支持，用于现场备料。",
      nodes: [
        { id: 'ex2_n1', type: 'schemaNode', position: { x: 100, y: 100 }, data: { label: 'Process' } },
        { id: 'ex2_n2', type: 'schemaNode', position: { x: 300, y: 100 }, data: { label: 'Tool' } },
      ],
      edges: [
        { id: 'ex2_e1', source: 'ex2_n1', target: 'ex2_n2', label: 'REQUIRES_TOOL', type: 'smoothstep', markerEnd: { type: MarkerType.ArrowClosed } }
      ]
    },
    {
      title: "合规性冲突检查",
      desc: "识别哪些旧规范已被新版替代，防止误用过期标准。",
      nodes: [
        { id: 'ex3_n1', type: 'schemaNode', position: { x: 100, y: 100 }, data: { label: 'Document' } },
        { id: 'ex3_n2', type: 'schemaNode', position: { x: 350, y: 100 }, data: { label: 'Document' } },
      ],
      edges: [
        { id: 'ex3_e1', source: 'ex3_n1', target: 'ex3_n2', label: 'SUPERSEDES', type: 'smoothstep', markerEnd: { type: MarkerType.ArrowClosed } }
      ]
    }
  ];

  const loadExample = (ex: any) => {
    setNodes(ex.nodes);
    setEdges(ex.edges);
    setShowTutorial(false);
    setTimeout(() => fitView({ duration: 800 }), 100);
  };

  // 获取 Schema
  useEffect(() => {
    fetch('/api/graph/schema')
      .then(res => res.json())
      .then(data => {
        setSchema({
          labels: data.labels.filter((l: string) => !l.startsWith('_')),
          relationship_types: data.relationship_types
        });
      });
  }, []);

  // 连线处理
  const onConnect = useCallback((params: any) => {
    setEdges((eds) => addEdge({ 
      ...params, 
      type: 'smoothstep', 
      markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1' },
      style: { stroke: '#6366f1', strokeWidth: 2 },
      label: 'HAS',
    }, eds));
  }, [setEdges]);

  const onEdgeClick = (_: any, edge: any) => {
    const nextType = prompt('输入关系类型 (例如: HAS_SECTION, REQUIRES_TOOL):', edge.label || 'HAS');
    if (nextType) {
      setEdges((eds) => eds.map(e => e.id === edge.id ? { ...e, label: nextType.toUpperCase() } : e));
    }
  };

  // Cypher 生成器
  useEffect(() => {
    if (nodes.length === 0) {
      setCypher('');
      return;
    }
    
    // 使用 node.id 映射为合法的 Cypher 变量名 (如 node_abc -> var_node_abc)
    const getVar = (id: string) => `v_${id.replace(/[^a-zA-Z0-9]/g, '_')}`;
    
    let clauses: string[] = [];
    nodes.forEach((node) => {
      clauses.push(`(${getVar(node.id)}:\`${node.data.label}\`)`);
    });
    
    edges.forEach((edge) => {
      const sourceNode = nodes.find(n => n.id === edge.source);
      const targetNode = nodes.find(n => n.id === edge.target);
      
      if (sourceNode && targetNode) {
        const relType = edge.label || 'HAS';
        clauses.push(`(${getVar(sourceNode.id)})-[:\`${relType}\`]->(${getVar(targetNode.id)})`);
      }
    });
    
    const cypherStr = `MATCH ${clauses.join(',\n      ')}\nRETURN * LIMIT 25`;
    setCypher(cypherStr);
  }, [nodes, edges]);

  const addNode = (label: string) => {
    const id = `node_${Math.random().toString(36).substr(2, 9)}`;
    setNodes((nds) => nds.concat({
      id,
      type: 'schemaNode',
      position: { x: 100 + Math.random() * 200, y: 100 + Math.random() * 200 },
      data: { label },
    }));
  };

  const runQuery = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/graph/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cypher })
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        setResults(null);
      } else {
        setResults(data);
      }
    } catch (err: any) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(cypher);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex h-screen bg-[#030712] text-gray-200 overflow-hidden font-sans">
      {/* Sidebar */}
      <div className="w-64 border-r border-gray-800 bg-gray-950/50 backdrop-blur-xl p-5 flex flex-col gap-6 z-20">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-600/20 rounded-lg">
            <Database className="text-indigo-500" size={20} />
          </div>
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
                  className="px-3 py-2.5 bg-gray-900/50 border border-gray-800 rounded-xl text-xs text-left 
                           hover:border-indigo-500/50 hover:bg-indigo-500/5 transition-all flex items-center justify-between group"
                >
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
              <p className="text-[10px] text-indigo-300/70 leading-relaxed">
                通过连接节点构建逻辑链路，系统将实时生成 Neo4j 标准 Cypher 查询语句。
              </p>
           </div>
        </div>
      </div>

      {/* Main Canvas */}
      <div className="flex-1 relative flex flex-col">
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgeClick={onEdgeClick}
            nodeTypes={nodeTypes}
            colorMode="dark"
            fitView
          >
            <Background color="#111827" gap={20} size={1} />
            <Controls className="!bg-gray-900 !border-gray-800 !fill-gray-400" />
            <MiniMap 
                nodeStrokeColor="#4f46e5" nodeColor="#1e1b4b" maskColor="rgba(0, 0, 0, 0.7)"
                style={{ background: '#030712', borderRadius: '12px', border: '1px solid #1f2937' }}
            />
            
            <Panel position="top-right" className="flex gap-2">
              <div className="bg-gray-900/80 backdrop-blur border border-gray-800 p-1 rounded-xl flex gap-1 shadow-2xl">
                <button onClick={() => setShowTutorial(true)}
                    className="flex items-center gap-2 px-3 py-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg text-sm transition-all"
                >
                    <HelpCircle size={16} />
                    使用指南
                </button>
                <div className="w-px h-4 bg-gray-800 self-center mx-1" />
                <button onClick={runQuery} disabled={!cypher || loading}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 
                             text-white rounded-lg text-sm font-bold transition-all shadow-lg shadow-indigo-500/20"
                >
                    <Play size={14} fill="currentColor" />
                    {loading ? '执行中...' : '运行查询'}
                </button>
                <button onClick={() => { setNodes([]); setEdges([]); setResults(null); setError(null); }}
                    className="p-2 text-gray-500 hover:text-red-400 transition-colors" title="清空画布"
                >
                    <Trash2 size={18} />
                </button>
              </div>
            </Panel>

            {showTutorial && (
               <Panel position="center" className="w-[500px] pointer-events-auto">
                  <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.5)] p-6 animate-in zoom-in-95 duration-200">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-indigo-500/20 rounded-lg">
                                <BookOpen className="text-indigo-400" size={20} />
                            </div>
                            <h2 className="text-lg font-bold text-white">Cypher 构造器快速上手</h2>
                        </div>
                        <button onClick={() => setShowTutorial(false)} className="text-gray-500 hover:text-white">
                            <X size={20} />
                        </button>
                    </div>

                    <div className="space-y-3">
                        {examples.map((ex, i) => (
                            <div key={i} onClick={() => loadExample(ex)}
                                className="group p-4 bg-gray-800/40 border border-gray-700 rounded-xl cursor-pointer 
                                         hover:border-indigo-500 hover:bg-indigo-500/5 transition-all"
                            >
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
                  <div className="bg-red-950/40 border border-red-500/50 backdrop-blur-md p-3 rounded-xl flex gap-3 shadow-2xl animate-in fade-in slide-in-from-top-4">
                    <AlertCircle className="text-red-400 shrink-0" size={18} />
                    <div className="flex-1 min-w-0">
                        <div className="text-xs font-bold text-red-300 uppercase mb-1">查询错误</div>
                        <div className="text-[11px] text-red-200/80 font-mono break-all">{error}</div>
                    </div>
                    <button onClick={() => setError(null)} className="text-red-400 hover:text-white transition-colors">
                        <X size={14} />
                    </button>
                  </div>
               </Panel>
            )}
          </ReactFlow>
        </div>

        {/* Bottom Panel */}
        <div className="h-72 border-t border-gray-800 bg-[#030712] flex shadow-[0_-10px_30px_rgba(0,0,0,0.5)] z-10">
          <div className="w-2/5 border-r border-gray-900 p-5 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                <Code size={14} className="text-indigo-500" /> Cypher 代码预览
              </div>
              <button className={`flex items-center gap-1.5 text-[10px] font-bold transition-colors ${copied ? 'text-emerald-400' : 'text-indigo-400 hover:text-indigo-300'}`}
                onClick={copyToClipboard}
              >
                {copied ? <CheckCircle2 size={12} /> : <Copy size={12} />} {copied ? '已复制' : '复制代码'}
              </button>
            </div>
            <div className="flex-1 bg-gray-900/30 rounded-xl p-4 font-mono text-sm overflow-auto border border-gray-800/50">
              {cypher ? <code className="text-indigo-300 block whitespace-pre leading-relaxed">{cypher}</code> : <div className="h-full flex flex-col items-center justify-center opacity-20 italic text-xs">// 从左侧添加实体并建立连线生成查询...</div>}
            </div>
          </div>

          <div className="w-3/5 p-5 flex flex-col">
             <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-[10px] font-bold text-gray-500 uppercase tracking-widest">
                    <Database size={14} className="text-emerald-500" /> 执行结果集
                    {results?.nodes && <span className="ml-2 px-1.5 py-0.5 bg-emerald-500/10 text-emerald-500 rounded text-[9px]">{results.nodes.length} 节点 / {results.edges.length} 关系</span>}
                </div>
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
                ) : <div className="h-full flex flex-col items-center justify-center opacity-20"><Database size={40} className="mb-2" /><p className="text-xs italic">等待查询执行结果...</p></div>}
              </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- 外部导出组件 ---
export default function CypherBuilderPage() {
  return (
    <ReactFlowProvider>
      <BuilderInternal />
    </ReactFlowProvider>
  );
}
