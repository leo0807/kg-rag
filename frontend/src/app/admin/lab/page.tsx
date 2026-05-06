"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { Save, Play, Check, Trash2 } from "lucide-react";
import { useLabParams } from "./useLabParams";

interface ABEntry {
    ts: number; question: string;
    label_a: string; params_a: Record<string, number>; result_a: { score_top1: number; count: number; latency_ms: number; error: string | null };
    label_b: string; params_b: Record<string, number>; result_b: { score_top1: number; count: number; latency_ms: number; error: string | null };
}

function Slider({ label, min, max, step, value, onChange }: { label: string; min: number; max: number; step: number; value: number; onChange: (v: number) => void }) {
    return (
        <div>
            <div className="flex justify-between mb-1"><span className="text-xs text-gray-400">{label}</span><span className="text-xs font-mono text-indigo-300">{value}</span></div>
            <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(parseFloat(e.target.value))} className="w-full accent-indigo-500 h-1.5 cursor-pointer" />
        </div>
    );
}

export default function LabPage() {
    const { params, update, save, saving, msg, presets, savePreset, deletePreset, loadPreset, applyAsDefault } = useLabParams();
    const [presetName, setPresetName] = useState("");
    const [history, setHistory] = useState<ABEntry[]>([]);
    const [abQ, setAbQ] = useState("");
    const [abRunning, setAbRunning] = useState(false);

    useEffect(() => {
        fetchApi<ABEntry[]>("/api/admin/lab/history").then(setHistory).catch(() => {});
    }, []);

    async function runAB() {
        if (!abQ.trim()) return;
        setAbRunning(true);
        try {
            const entry = await fetchApi<ABEntry>("/api/admin/lab/run-ab", {
                method: "POST",
                body: JSON.stringify({
                    question: abQ,
                    params_a: params,            label_a: "当前参数",
                    params_b: { ...params, alpha: params.alpha > 0.5 ? 0.2 : 0.8 }, label_b: "对比参数",
                }),
            });
            setHistory(h => [entry, ...h.slice(0, 19)]);
        } finally { setAbRunning(false); }
    }

    async function handleSavePreset() {
        if (!presetName.trim()) return;
        await savePreset(presetName.trim()); setPresetName("");
    }

    return (
        <div className="p-6 max-w-5xl mx-auto space-y-6">
            <div className="flex items-start justify-between">
                <div><h1 className="text-xl font-semibold text-white">检索权重实验室</h1>
                    <p className="text-xs text-gray-500 mt-0.5">调整各检索阶段权重并进行 A/B 对比实验</p></div>
                <div className="flex gap-2">
                    {msg && <span className="flex items-center gap-1 text-xs text-green-400 px-2"><Check size={12} />{msg}</span>}
                    <button onClick={() => save()} disabled={saving}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-indigo-600 text-white text-xs hover:bg-indigo-500 disabled:opacity-40">
                        <Save size={12} />{saving ? "保存中..." : "保存配置"}
                    </button>
                    <button onClick={applyAsDefault}
                        className="px-3 py-1.5 rounded bg-green-600/20 border border-green-500/30 text-green-300 text-xs hover:bg-green-600/30">
                        应用为全局默认
                    </button>
                </div>
            </div>

            {/* Presets */}
            <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl">
                <div className="text-xs font-medium text-gray-400 mb-3">参数预设</div>
                <div className="flex flex-wrap gap-2 mb-3">
                    {presets.map(p => (
                        <div key={p.name} className="flex items-center gap-1 pl-3 pr-1 py-1 rounded-lg bg-gray-800 border border-gray-700">
                            <button onClick={() => loadPreset(p)} className="text-xs text-gray-300 hover:text-white">{p.name}</button>
                            <button onClick={() => deletePreset(p.name)} className="p-0.5 text-gray-600 hover:text-red-400"><Trash2 size={10} /></button>
                        </div>
                    ))}
                    {presets.length === 0 && <span className="text-xs text-gray-600">暂无预设</span>}
                </div>
                <div className="flex gap-2">
                    <input value={presetName} onChange={e => setPresetName(e.target.value)} placeholder="预设名称..."
                        className="flex-1 px-2.5 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500" />
                    <button onClick={handleSavePreset} disabled={!presetName.trim()} className="px-3 py-1.5 rounded bg-gray-700 text-xs text-gray-300 hover:bg-gray-600 disabled:opacity-40">保存当前为预设</button>
                </div>
            </div>

            {/* Params grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl space-y-4">
                    <div className="text-xs font-medium text-indigo-400 mb-1">向量检索</div>
                    <Slider label="Embedding 权重" min={0} max={2} step={0.1} value={params.vector_weight} onChange={v => update("vector_weight", v)} />
                    <Slider label="相似度阈值" min={0} max={1} step={0.05} value={params.similarity_threshold} onChange={v => update("similarity_threshold", v)} />
                    <div><div className="flex justify-between mb-1"><span className="text-xs text-gray-400">最大召回数</span><span className="text-xs font-mono text-indigo-300">{params.max_recall}</span></div>
                        <input type="number" min={1} max={100} value={params.max_recall} onChange={e => update("max_recall", parseInt(e.target.value))}
                            className="w-full px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500" /></div>
                </div>
                <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl space-y-4">
                    <div className="text-xs font-medium text-amber-400 mb-1">BM25 检索</div>
                    <Slider label="BM25 权重" min={0} max={2} step={0.1} value={params.bm25_weight} onChange={v => update("bm25_weight", v)} />
                    <Slider label="标题字段权重" min={1} max={5} step={0.5} value={params.title_weight} onChange={v => update("title_weight", v)} />
                    <div><div className="text-xs text-gray-400 mb-1">模糊匹配程度</div>
                        <select value={params.fuzzy_match} onChange={e => update("fuzzy_match", e.target.value)}
                            className="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-400 outline-none">
                            {["auto", "none", "low", "medium", "high"].map(v => <option key={v} value={v}>{v}</option>)}
                        </select></div>
                </div>
                <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl space-y-4">
                    <div className="text-xs font-medium text-emerald-400 mb-1">融合 / 图谱</div>
                    <Slider label="Alpha (BM25 vs 向量)" min={0} max={1} step={0.05} value={params.alpha} onChange={v => update("alpha", v)} />
                    <div><div className="flex justify-between mb-1"><span className="text-xs text-gray-400">RRF 常数 K</span><span className="text-xs font-mono text-indigo-300">{params.rrf_k}</span></div>
                        <input type="number" min={1} max={200} value={params.rrf_k} onChange={e => update("rrf_k", parseInt(e.target.value))}
                            className="w-full px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500" /></div>
                    <div><div className="text-xs text-gray-400 mb-1">图谱扩展跳数</div>
                        <div className="flex gap-1">{[1,2,3].map(h => <button key={h} onClick={() => update("graph_hops", h)}
                            className={`flex-1 py-1 rounded text-xs transition-colors ${params.graph_hops === h ? "bg-indigo-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{h}跳</button>)}</div></div>
                </div>
            </div>

            {/* A/B Test */}
            <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl">
                <div className="text-xs font-medium text-gray-400 mb-3">A/B 实验（当前参数 vs 对比参数）</div>
                <div className="flex gap-2">
                    <input value={abQ} onChange={e => setAbQ(e.target.value)} placeholder="输入测试问题..."
                        className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 outline-none focus:border-indigo-500 placeholder-gray-600" />
                    <button onClick={runAB} disabled={abRunning || !abQ.trim()}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-600/20 border border-amber-500/30 text-amber-300 text-sm hover:bg-amber-600/30 disabled:opacity-40">
                        <Play size={12} />{abRunning ? "运行中..." : "运行对比"}
                    </button>
                </div>
            </div>

            {/* History */}
            {history.length > 0 && (
                <div className="rounded-xl border border-gray-800 overflow-hidden">
                    <div className="px-4 py-2.5 bg-gray-900 border-b border-gray-800 text-xs font-medium text-gray-400">A/B 历史对比</div>
                    <table className="w-full text-xs">
                        <thead className="text-gray-500 bg-gray-900/50">
                            <tr><th className="px-3 py-2 text-left">时间</th><th className="px-3 py-2 text-left">问题</th>
                                <th className="px-3 py-2 text-left">策略A</th><th className="px-3 py-2 text-left">策略B</th></tr>
                        </thead>
                        <tbody className="divide-y divide-gray-800/60">
                            {history.map((e, i) => (
                                <tr key={i} className="hover:bg-gray-900/40">
                                    <td className="px-3 py-2 text-gray-600 whitespace-nowrap font-mono">{new Date(e.ts * 1000).toLocaleTimeString("zh-CN")}</td>
                                    <td className="px-3 py-2 text-gray-300 max-w-[160px] truncate">{e.question}</td>
                                    <td className="px-3 py-2 text-gray-400">{e.label_a} · {e.result_a.latency_ms}ms · Top1={e.result_a.score_top1}</td>
                                    <td className="px-3 py-2 text-gray-400">{e.label_b} · {e.result_b.latency_ms}ms · Top1={e.result_b.score_top1}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
