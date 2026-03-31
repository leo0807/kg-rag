"use client";
import { useState, useEffect, useCallback } from "react";
import { Search, Trash2, Merge, RefreshCw, Filter } from "lucide-react";
import { fetchApi } from "@/lib/api";

type EntityType = "Tool" | "Material" | "Process";

interface Entity {
    type: string;
    name: string;
    doc_id: string;
}

interface EntitiesResponse {
    entities: Entity[];
    total: number;
}

const TYPE_COLOR: Record<EntityType, string> = {
    Tool:     "bg-emerald-900/40 text-emerald-400 border-emerald-800",
    Material: "bg-orange-900/40 text-orange-400 border-orange-800",
    Process:  "bg-purple-900/40 text-purple-400 border-purple-800",
};

export default function EntityAuditPage() {
    const [entities, setEntities] = useState<Entity[]>([]);
    const [loading,  setLoading]  = useState(false);
    const [typeFilter, setTypeFilter] = useState<EntityType | "">("");
    const [search, setSearch]     = useState("");
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [mergeTarget, setMergeTarget] = useState("");
    const [merging, setMerging]   = useState(false);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (typeFilter) params.set("type", typeFilter);
            if (search)     params.set("q", search);
            const data = await fetchApi<EntitiesResponse>(`/api/entities?${params}`);
            setEntities(data.entities);
        } finally {
            setLoading(false);
        }
    }, [typeFilter, search]);

    useEffect(() => { load(); }, [load]);

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
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` },
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
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({
                    source_names: Array.from(selected),
                    target_name:  mergeTarget,
                    type:         typeFilter || "Tool",
                }),
            });
            setSelected(new Set());
            setMergeTarget("");
            await load();
        } finally {
            setMerging(false);
        }
    }

    const counts = entities.reduce<Record<string, number>>((acc, e) => {
        acc[e.type] = (acc[e.type] || 0) + 1;
        return acc;
    }, {});

    return (
        <div className="flex flex-col h-full bg-gray-950">
            {/* Header */}
            <div className="px-6 py-4 border-b border-gray-800">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h1 className="text-lg font-semibold text-white">实体审核</h1>
                        <p className="text-xs text-gray-500 mt-0.5">
                            管理自动提取的 Tool / Material / Process 节点，支持合并和删除
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        {(["Tool", "Material", "Process"] as EntityType[]).map(t => (
                            <span key={t} className={`px-2 py-0.5 rounded border text-xs ${TYPE_COLOR[t]}`}>
                                {t} {counts[t] || 0}
                            </span>
                        ))}
                    </div>
                </div>

                {/* Controls */}
                <div className="flex flex-wrap items-center gap-3">
                    <div className="relative">
                        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
                        <input
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder="搜索实体名称..."
                            className="pl-8 pr-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg
                                       text-sm text-gray-200 outline-none focus:border-indigo-500 w-52"
                        />
                    </div>

                    <div className="flex items-center gap-1">
                        <Filter size={13} className="text-gray-500" />
                        {(["", "Tool", "Material", "Process"] as (EntityType | "")[]).map(t => (
                            <button key={t} onClick={() => setTypeFilter(t)}
                                className={`px-2.5 py-1 rounded text-xs transition-colors ${
                                    typeFilter === t ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"
                                }`}>
                                {t || "全部"}
                            </button>
                        ))}
                    </div>

                    <button onClick={load} className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors">
                        <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
                    </button>

                    {/* Merge panel */}
                    {selected.size > 0 && (
                        <div className="flex items-center gap-2 ml-auto bg-gray-900 border border-indigo-700 rounded-lg px-3 py-1.5">
                            <span className="text-xs text-indigo-400">已选 {selected.size} 个</span>
                            <input
                                value={mergeTarget}
                                onChange={e => setMergeTarget(e.target.value)}
                                placeholder="合并目标名称..."
                                className="px-2 py-0.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500 w-40"
                            />
                            <button
                                onClick={mergeSelected}
                                disabled={merging}
                                className="flex items-center gap-1 px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700
                                           rounded text-xs text-white disabled:opacity-50 transition-colors"
                            >
                                <Merge size={12} />
                                合并
                            </button>
                            <button onClick={() => setSelected(new Set())}
                                className="text-xs text-gray-500 hover:text-white transition-colors">
                                取消
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto">
                {loading ? (
                    <div className="flex items-center justify-center h-48 text-gray-500 text-sm">加载中...</div>
                ) : entities.length === 0 ? (
                    <div className="flex items-center justify-center h-48 text-gray-600 text-sm">暂无实体数据</div>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-800 text-left">
                                <th className="px-4 py-2.5 w-8">
                                    <input type="checkbox"
                                        checked={selected.size === entities.length && entities.length > 0}
                                        onChange={e => {
                                            if (e.target.checked) setSelected(new Set(entities.map(e => e.name)));
                                            else setSelected(new Set());
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
                                        <input type="checkbox"
                                            checked={selected.has(entity.name)}
                                            onChange={() => toggleSelect(entity.name)}
                                            className="rounded border-gray-600" />
                                    </td>
                                    <td className="px-4 py-2.5 text-gray-200">{entity.name}</td>
                                    <td className="px-4 py-2.5">
                                        <span className={`px-2 py-0.5 rounded border text-xs ${TYPE_COLOR[entity.type as EntityType] || "bg-gray-800 text-gray-400 border-gray-700"}`}>
                                            {entity.type}
                                        </span>
                                    </td>
                                    <td className="px-4 py-2.5 text-xs text-gray-500 font-mono">{entity.doc_id || "—"}</td>
                                    <td className="px-4 py-2.5 text-right">
                                        <button
                                            onClick={() => deleteEntity(entity.name, entity.type)}
                                            className="p-1 rounded text-gray-600 hover:text-red-400 hover:bg-gray-800 transition-colors"
                                            title="删除">
                                            <Trash2 size={13} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
}
