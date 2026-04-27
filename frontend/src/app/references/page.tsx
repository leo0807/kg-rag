"use client";

import { RotateCcw, Search, X } from "lucide-react";
import { useReferences } from "./useReferences";
import { ReferenceGraph } from "./ReferenceGraph";
import { ReferenceDetailPanel } from "./ReferenceDetailPanel";

export default function ReferencesPage() {
    const {
        nodes, edges, stats, focusId, setFocusId, depth, setDepth,
        search, setSearch, selected, setSelected, loading,
        filtered, outNeighbors, inNeighbors,
    } = useReferences();

    return (
        <div className="flex h-full bg-gray-950 overflow-hidden">

            {/* 左侧控制面板 */}
            <div className="w-56 shrink-0 flex flex-col border-r border-gray-800 bg-gray-900 overflow-y-auto">
                <div className="px-4 py-4 border-b border-gray-800">
                    <h1 className="text-sm font-bold text-white">引用关系图</h1>
                    <p className="text-xs text-gray-500 mt-0.5">文档间规范引用网络</p>
                </div>

                <div className="px-3 py-3 border-b border-gray-800">
                    <div className="relative">
                        <Search size={13} className="absolute left-2.5 top-2 text-gray-500" />
                        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索文档编号…"
                            className="w-full pl-8 pr-2 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-200 placeholder-gray-600 outline-none focus:border-indigo-500" />
                    </div>
                    {filtered.length > 0 && (
                        <div className="mt-1 bg-gray-800 border border-gray-700 rounded-lg overflow-hidden max-h-40 overflow-y-auto">
                            {filtered.map(n => (
                                <button key={n.id}
                                    onClick={() => { setFocusId(n.id); setSearch(""); setSelected(null); }}
                                    className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700 truncate">
                                    <span className="font-mono text-indigo-400">{n.id}</span>
                                    <span className="text-gray-500 ml-1">{n.title.slice(0, 20)}</span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {focusId && (
                    <div className="px-3 py-2 border-b border-gray-800 flex items-center gap-2">
                        <span className="text-xs text-indigo-400 font-mono truncate flex-1">{focusId}</span>
                        <button onClick={() => { setFocusId(""); setSelected(null); }} className="text-gray-500 hover:text-white">
                            <X size={12} />
                        </button>
                    </div>
                )}

                {focusId && (
                    <div className="px-3 py-3 border-b border-gray-800">
                        <div className="text-xs text-gray-500 mb-2">扩散深度</div>
                        <div className="flex gap-1">
                            {[1, 2].map(d => (
                                <button key={d} onClick={() => setDepth(d)}
                                    className={`flex-1 py-1 text-xs rounded border transition-colors ${
                                        depth === d ? "bg-indigo-600 border-indigo-500 text-white" : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white"
                                    }`}>
                                    {d} 跳
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {stats && (
                    <div className="px-3 py-3 border-b border-gray-800 space-y-2">
                        <div className="text-xs text-gray-500 uppercase tracking-wider">统计</div>
                        <div className="text-xs text-gray-300">
                            <div className="flex justify-between"><span className="text-gray-500">文档数</span><span>{stats.total_docs}</span></div>
                            <div className="flex justify-between mt-1"><span className="text-gray-500">引用数</span><span>{stats.total_refs}</span></div>
                            {stats.most_cited && (
                                <div className="mt-2 px-2 py-1.5 bg-amber-950/30 border border-amber-800/40 rounded-lg">
                                    <div className="text-amber-400/70 text-[10px] mb-0.5">被引最多</div>
                                    <div className="text-amber-300 font-mono text-xs">{stats.most_cited.doc_id}</div>
                                    <div className="text-amber-400/60 text-[10px]">{stats.most_cited.count} 次</div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                <div className="px-3 py-3 space-y-1.5">
                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">图例</div>
                    {[["#22c55e", "当前文档"], ["#f59e0b", "核心文档（≥5次被引）"], ["#6366f1", "普通文档"]].map(([color, label]) => (
                        <div key={label} className="flex items-center gap-2">
                            <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color }} />
                            <span className="text-xs text-gray-400">{label}</span>
                        </div>
                    ))}
                </div>

                <div className="mt-auto px-3 py-3 border-t border-gray-800">
                    <button onClick={() => { setFocusId(""); setDepth(1); setSelected(null); }}
                        className="w-full flex items-center justify-center gap-1.5 py-1.5 text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg transition-colors">
                        <RotateCcw size={12} /> 重置视图
                    </button>
                </div>
            </div>

            <ReferenceGraph nodes={nodes} edges={edges} loading={loading} onSelect={setSelected} />

            {selected && (
                <ReferenceDetailPanel
                    selected={selected}
                    outNeighbors={outNeighbors}
                    inNeighbors={inNeighbors}
                    onClose={() => setSelected(null)}
                    onFocus={(id) => { setFocusId(id); setSelected(null); }}
                />
            )}
        </div>
    );
}
