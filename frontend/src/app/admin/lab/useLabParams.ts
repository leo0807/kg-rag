import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

export interface LabParams {
    alpha: number; top_k: number;
    vector_weight: number; similarity_threshold: number; max_recall: number;
    bm25_weight: number; title_weight: number; fuzzy_match: string;
    rrf_k: number; rerank_top_k: number; graph_hops: number;
}

export interface Preset { name: string; params: LabParams; }

export const DEFAULT_PARAMS: LabParams = {
    alpha: 0.5, top_k: 5,
    vector_weight: 1.0, similarity_threshold: 0.0, max_recall: 20,
    bm25_weight: 1.0, title_weight: 2.0, fuzzy_match: "auto",
    rrf_k: 60, rerank_top_k: 5, graph_hops: 1,
};

export function useLabParams() {
    const [params, setParams]   = useState<LabParams>(DEFAULT_PARAMS);
    const [presets, setPresets] = useState<Preset[]>([]);
    const [saving, setSaving]   = useState(false);
    const [msg, setMsg]         = useState("");

    const loadPresets = useCallback(async () => {
        try { setPresets(await fetchApi<Preset[]>("/api/admin/lab/presets")); } catch { /* ignore */ }
    }, []);

    useEffect(() => {
        fetchApi<LabParams>("/api/admin/lab/params").then(setParams).catch(() => {});
        loadPresets();
    }, [loadPresets]);

    async function save(msg = "已保存") {
        setSaving(true);
        try {
            await fetchApi("/api/admin/lab/params", { method: "PUT", body: JSON.stringify({ params }) });
            setMsg(msg); setTimeout(() => setMsg(""), 2500);
        } finally { setSaving(false); }
    }

    async function savePreset(name: string) {
        await fetchApi("/api/admin/lab/presets", { method: "POST", body: JSON.stringify({ name, params }) });
        await loadPresets();
    }

    async function deletePreset(name: string) {
        await fetchApi(`/api/admin/lab/presets/${encodeURIComponent(name)}`, { method: "DELETE" });
        await loadPresets();
    }

    async function applyAsDefault() {
        await fetchApi("/api/admin/lab/apply", { method: "POST", body: JSON.stringify({ params }) });
        setMsg("已应用为全局默认"); setTimeout(() => setMsg(""), 2500);
    }

    function loadPreset(p: Preset) { setParams(p.params); }

    function update(key: keyof LabParams, value: number | string) {
        setParams(prev => ({ ...prev, [key]: value }));
    }

    return { params, update, save, saving, msg, presets, savePreset, deletePreset, loadPreset, applyAsDefault };
}
