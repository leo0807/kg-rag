"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { Search, Trash2, Merge, RefreshCw, Filter, HelpCircle, X } from "lucide-react";
import { fetchApi } from "@/lib/api";

type EntityType = "Tool" | "Material" | "Process";

interface Entity { type: string; name: string; doc_id: string; }
interface EntitiesResponse {
    entities: Entity[]; total: number; page: number; per_page: number; pages: number;
}

const TYPE_COLOR: Record<EntityType, string> = {
    Tool:     "bg-emerald-900/40 text-emerald-400 border-emerald-800",
    Material: "bg-orange-900/40 text-orange-400 border-orange-800",
    Process:  "bg-purple-900/40 text-purple-400 border-purple-800",
};

const PER_PAGE = 50;

export default function EntityAuditPage() {
    const [entities,   setEntities]   = useState<Entity[]>([]);
    const [loading,    setLoading]    = useState(true);
    const [typeFilter, setTypeFilter] = useState<EntityType | "">("");
    const [searchInput,setSearchInput]= useState("");
    const [search,     setSearch]     = useState("");
    const [page,       setPage]       = useState(1);
    const [total,      setTotal]      = useState(0);
    const [selected,   setSelected]   = useState<Set<string>>(new Set());
    const [mergeTarget,setMergeTarget]= useState("");
    const [merging,    setMerging]    = useState(false);
    const [showHelp,   setShowHelp]   = useState(false);
    const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (typeFilter) params.set("type", typeFilter);
            if (search)     params.set("q", search);
            params.set("page",     String(page));
            params.set("per_page", String(PER_PAGE));
            const data = await fetchApi<EntitiesResponse>(`/api/entities?${params}`);
            setEntities(data.entities);
            setTotal(data.total);
        } finally {
            setLoading(false);
        }
    }, [typeFilter, search, page]);

    useEffect(() => { load(); }, [load]);

    const handleSearchInput = (val: string) => {
        setSearchInput(val);
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => { setSearch(val); setPage(1); }, 400);
    };

    function toggleSelect(name: string) {
        setSelected(prev => {
            const next = new Set(prev);
            if (next.has(name)) next.delete(name); else next.add(name);
            return next;
        });
    }

    async function deleteEntity(name: string, type: string) {
        if (!confirm(`确认删除实体「${name}」？此操作不可撤销。`)) return;
        const token = typeof window !== "undefined" ? localStorage.getItem("token") || "" : "";
        await fetch(`/api/admin/entities/${encodeURIComponent(name)}?type=${type}`, {
            method: "DELETE", headers: { Authorization: `Bearer ${token}` },
        });
        await load();
    }

    async function mergeSelected() {
        if (!mergeTarget.trim()) { alert("请输入合并目标名称"); return; }
        if (selected.size === 0) { alert("请选择要合并的实体"); return; }
        if (!confirm(`将选中的 ${selected.size} 个实体合并为「${mergeTarget}」？`)) return;
        setMerging(true);
        const token = typeof window !== "undefined" ? localStorage.getItem("token") || "" : "";
        try {
            await fetch("/api/admin/entities/merge", {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify({ source_names: Array.from(selected), target_name: mergeTarget, type: typeFilter || "Tool" }),
            });
            setSelected(new Set()); setMergeTarget(""); await load();
        } finally { setMerging(false); }
    }

    const pages = Math.ceil(total / PER_PAGE) || 1;

    return (
        <div className="flex flex-col h-full bg-gray-950">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-800 shrink-0">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <h1 className="text-lg font-semibold text-white">实体审核</h1>
                        <p className="text-xs text-gray-500 mt-0.5">管理自动提取的 Tool / Material / Process 节点，支持合并和删除</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">{total} 条实体</span>
                        <button onClick={() => setShowHelp(v => !v)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 border border-gray-700 transition-colors ml-2">
                            <HelpCircle size={13} />功能说明
                        </button>
                    </div>
                </div>

                {showHelp && (
                    <div className="mb-3 bg-indigo-950/30 border border-indigo-800/40 rounded-xl p-4 relative">
                        <button onClick={() => setShowHelp(false)} className="absolute top-3 right-3 text-gray-500 hover:text-white transition-colors"><X size={13} /></button>
                        <h3 className="text-xs font-semibold text-indigo-300 mb-2">这个页面是做什么的？</h3>
                        <p className="text-xs text-gray-300 leading-relaxed mb-2">
                            系统在读取文档时会自动识别出专业名词，例如工具名称、材料名称和工艺操作。但自动识别难免会产生重复或拼写不一的条目（如"扭矩扳手"和"扭力扳手"其实是同一件工具）。本页面让管理员能够整理这些条目，从而提升问答的准确性。
                        </p>
                        <div className="space-y-1 text-xs text-gray-400">
                            <div className="flex items-start gap-2"><span className="text-indigo-400 shrink-0">•</span><span><span className="text-emerald-400">Tool（工具）</span>：扳手、夹具、量具等操作工具</span></div>
                            <div className="flex items-start gap-2"><span className="text-indigo-400 shrink-0">•</span><span><span className="text-orange-400">Material（材料）</span>：金属板材、密封剂、涂层等原材料</span></div>
                            <div className="flex items-start gap-2"><span className="text-indigo-400 shrink-0">•</span><span><span className="text-purple-400">Process（工艺）</span>：热处理、铆接、涂装等工艺步骤</span></div>
                            <div className="flex items-start gap-2 mt-1.5"><span className="text-indigo-400 shrink-0">•</span><span>勾选多个条目后可以「合并」为统一名称；对错误条目可以直接「删除」。</span></div>
                        </div>
                    </div>
                )}

                <div className="flex flex-wrap items-center gap-3">
                    <div className="relative">
                        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
                        <input value={searchInput} onChange={e => handleSearchInput(e.target.value)}
                            placeholder="搜索实体名称..."
                            className="pl-8 pr-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 outline-none focus:border-indigo-500 w-52" />
                    </div>

                    <div className="flex items-center gap-1">
                        <Filter size={13} className="text-gray-500" />
                        {(["", "Tool", "Material", "Process"] as (EntityType | "")[]).map(t => (
                            <button key={t} onClick={() => { setTypeFilter(t); setPage(1); }}
                                className={`px-2.5 py-1 rounded text-xs transition-colors ${typeFilter === t ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"}`}>
                                {t || "全部"}
                            </button>
                        ))}
                    </div>

                    <button onClick={load} className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors">
                        <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
                    </button>

                    {selected.size > 0 && (
                        <div className="flex items-center gap-2 ml-auto bg-gray-900 border border-indigo-700 rounded-lg px-3 py-1.5">
                            <span className="text-xs text-indigo-400">已选 {selected.size} 个</span>
                            <input value={mergeTarget} onChange={e => setMergeTarget(e.target.value)}
                                placeholder="合并目标名称..."
                                className="px-2 py-0.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500 w-40" />
                            <button onClick={mergeSelected} disabled={merging}
                                className="flex items-center gap-1 px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 rounded text-xs text-white disabled:opacity-50 transition-colors">
                                <Merge size={12} />合并
                            </button>
                            <button onClick={() => setSelected(new Set())} className="text-xs text-gray-500 hover:text-white transition-colors">取消</button>
                        </div>
                    )}
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto">
                {entities.length === 0 && loading ? (
                    <div className="flex items-center justify-center h-48 text-gray-500 text-sm">加载中...</div>
                ) : entities.length === 0 ? (
                    <div className="flex items-center justify-center h-48 text-gray-600 text-sm">暂无实体数据</div>
                ) : (
                    <div className="relative">
                        {loading && <div className="absolute inset-0 bg-gray-950/50 z-10 pointer-events-none" />}
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-gray-800 text-left">
                                    <th className="px-4 py-2.5 w-8">
                                        <input type="checkbox"
                                            checked={entities.length > 0 && entities.every(e => selected.has(e.name))}
                                            onChange={ev => {
                                                if (ev.target.checked) setSelected(prev => new Set([...prev, ...entities.map(e => e.name)]));
                                                else setSelected(prev => { const next = new Set(prev); entities.forEach(e => next.delete(e.name)); return next; });
                                            }}
                                            className="rounded border-gray-600" />
                                    </th>
                                    <th className="px-4 py-2.5 text-xs text-gray-500 font-medium">名称</th>
                                    <th className="px-4 py-2.5 text-xs text-gray-500 font-medium">类型</th>
                                    <th className="px-4 py-2.5 text-xs text-gray-500 font-medium">所属文档</th>
                                    <th className="px-4 py-2.5 text-xs text-gray-500 font-medium w-16"></th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-800/50">
                                {entities.map(entity => (
                                    <tr key={`${entity.type}-${entity.name}`}
                                        className={`hover:bg-gray-900 transition-colors ${selected.has(entity.name) ? "bg-indigo-950/20" : ""}`}>
                                        <td className="px-4 py-2.5">
                                            <input type="checkbox" checked={selected.has(entity.name)} onChange={() => toggleSelect(entity.name)} className="rounded border-gray-600" />
                                        </td>
                                        <td className="px-4 py-2.5 text-gray-200">{entity.name}</td>
                                        <td className="px-4 py-2.5">
                                            <span className={`px-2 py-0.5 rounded border text-xs ${TYPE_COLOR[entity.type as EntityType] || "bg-gray-800 text-gray-400 border-gray-700"}`}>
                                                {entity.type}
                                            </span>
                                        </td>
                                        <td className="px-4 py-2.5 text-xs text-gray-500 font-mono">{entity.doc_id || "—"}</td>
                                        <td className="px-4 py-2.5 text-right">
                                            <button onClick={() => deleteEntity(entity.name, entity.type)}
                                                className="p-1 rounded text-gray-600 hover:text-red-400 hover:bg-gray-800 transition-colors" title="删除">
                                                <Trash2 size={13} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Pagination */}
            {total > PER_PAGE && (
                <div className="flex items-center justify-center gap-3 py-3 border-t border-gray-800 shrink-0 text-xs text-gray-500">
                    <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                        className="px-3 py-1 bg-gray-900 border border-gray-700 rounded text-gray-300 hover:border-gray-500 disabled:opacity-40 transition-colors">
                        上一页
                    </button>
                    <span>第 {page} / {pages} 页 · 共 {total} 条</span>
                    <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page >= pages}
                        className="px-3 py-1 bg-gray-900 border border-gray-700 rounded text-gray-300 hover:border-gray-500 disabled:opacity-40 transition-colors">
                        下一页
                    </button>
                </div>
            )}
        </div>
    );
}
