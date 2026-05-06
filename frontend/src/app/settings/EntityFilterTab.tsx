"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { Plus, Trash2 } from "lucide-react";

interface FilterRule {
    id: string; entity_name: string; entity_type: string;
    filter_type: string; reason: string; created_at: string;
}

const ENTITY_TYPES = ["", "Tool", "Material", "Process", "Entity"];
const TYPE_LABEL: Record<string, string> = { blacklist: "黑名单", whitelist: "白名单" };
const TYPE_STYLE: Record<string, string> = {
    blacklist: "bg-red-500/10 text-red-400 border border-red-500/20",
    whitelist: "bg-green-500/10 text-green-400 border border-green-500/20",
};

function AddRow({ filterType, onAdded }: { filterType: "blacklist" | "whitelist"; onAdded: () => void }) {
    const [name, setName]   = useState("");
    const [etype, setEtype] = useState("");
    const [reason, setReason] = useState("");
    const [saving, setSaving] = useState(false);

    async function submit() {
        if (!name.trim()) return;
        setSaving(true);
        try {
            await fetchApi("/api/entity-filters", {
                method: "POST", body: JSON.stringify({ entity_name: name.trim(), entity_type: etype, filter_type: filterType, reason }),
            });
            setName(""); setEtype(""); setReason("");
            onAdded();
        } finally { setSaving(false); }
    }

    return (
        <div className="flex items-center gap-2 mt-2">
            <input value={name} onChange={e => setName(e.target.value)} placeholder="实体名称"
                className="flex-1 px-2.5 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500" />
            <select value={etype} onChange={e => setEtype(e.target.value)}
                className="px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-400 outline-none">
                {ENTITY_TYPES.map(t => <option key={t} value={t}>{t || "类型"}</option>)}
            </select>
            <input value={reason} onChange={e => setReason(e.target.value)} placeholder="原因"
                className="w-32 px-2.5 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500" />
            <button onClick={submit} disabled={saving || !name.trim()}
                className="flex items-center gap-1 px-3 py-1.5 rounded bg-indigo-600 text-white text-xs hover:bg-indigo-500 disabled:opacity-40">
                <Plus size={11} />{saving ? "添加中..." : "添加"}
            </button>
        </div>
    );
}

export function EntityFilterTab() {
    const [rules, setRules]   = useState<FilterRule[]>([]);
    const [loading, setLoading] = useState(true);

    const load = useCallback(async () => {
        setLoading(true);
        try { setRules(await fetchApi<FilterRule[]>("/api/entity-filters")); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { load(); }, [load]);

    async function remove(id: string) {
        await fetchApi(`/api/entity-filters/${id}`, { method: "DELETE" });
        setRules(r => r.filter(x => x.id !== id));
    }

    const blacklist = rules.filter(r => r.filter_type === "blacklist");
    const whitelist = rules.filter(r => r.filter_type === "whitelist");

    function renderSection(type: "blacklist" | "whitelist", items: FilterRule[]) {
        return (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                    <div>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${TYPE_STYLE[type]}`}>{TYPE_LABEL[type]}</span>
                        <span className="ml-2 text-xs text-gray-500">
                            {type === "blacklist" ? "降低相关内容的检索权重 (×0.3)" : "优先返回相关内容"}
                        </span>
                    </div>
                    <span className="text-xs text-gray-600">{items.length} 条规则</span>
                </div>
                {items.length > 0 && (
                    <div className="space-y-1.5 mb-3">
                        {items.map(r => (
                            <div key={r.id} className="flex items-center gap-2 px-3 py-2 bg-gray-800/60 rounded-lg">
                                <span className="text-xs text-gray-200 font-medium min-w-0 flex-1">{r.entity_name}</span>
                                {r.entity_type && <span className="text-xs text-gray-500 px-1.5 py-0.5 bg-gray-700 rounded">{r.entity_type}</span>}
                                {r.reason && <span className="text-xs text-gray-600 truncate max-w-[120px]">{r.reason}</span>}
                                <button onClick={() => remove(r.id)} className="text-gray-600 hover:text-red-400 transition-colors ml-auto">
                                    <Trash2 size={12} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
                <AddRow filterType={type} onAdded={load} />
            </div>
        );
    }

    if (loading) return <div className="text-gray-500 text-sm py-4">加载中...</div>;

    return (
        <div className="space-y-4">
            {renderSection("blacklist", blacklist)}
            {renderSection("whitelist", whitelist)}
        </div>
    );
}
