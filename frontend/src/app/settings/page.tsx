"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface Settings {
    embedding_mode: string;
    embedding_model: string;
    embedding_api_url: string;
    embedding_api_key: string;
    reranker_mode: string;
    reranker_model: string;
    reranker_api_url: string;
    reranker_api_key: string;
    llm_mode: string;
    llm_api_url: string;
    llm_api_key: string;
    llm_model: string;
    query_top_k: string;
    query_strategy: string;
}

export default function SettingsPage() {
    const [settings, setSettings] = useState<Settings | null>(null);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);

    useEffect(() => {
        const token = localStorage.getItem("token");
        fetch("/api/settings/user", {
            headers: { "Authorization": `Bearer ${token}` },
        })
            .then(r => r.json())
            .then(setSettings);
    }, []);

    async function handleSave() {
        if (!settings) return;
        setSaving(true);
        try {
            const token = localStorage.getItem("token");
            await fetch("/api/settings/user", {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`,
                },
                body: JSON.stringify({ settings }),
            });
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        } finally {
            setSaving(false);
        }
    }

    if (!settings) {
        return <div className="p-8 text-gray-500 text-sm">加载中...</div>;
    }

    return (
        <div className="p-8 max-w-2xl">
            <h1 className="text-2xl font-semibold text-white mb-8">设置</h1>

            {/* Embedding 配置 */}
            <section className="mb-8">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-4">
                    Embedding 模型
                </div>
                <div className="space-y-4 bg-gray-900 rounded-xl p-4 border border-gray-800">
                    <div className="flex gap-3">
                        {["local", "api"].map(mode => (
                            <button
                                key={mode}
                                onClick={() => setSettings(s => s ? { ...s, embedding_mode: mode } : s)}
                                className={`px-3 py-1.5 rounded text-xs border transition-colors ${settings.embedding_mode === mode
                                        ? "bg-indigo-600 border-indigo-600 text-white"
                                        : "border-gray-700 text-gray-400 hover:border-gray-500"
                                    }`}
                            >
                                {mode === "local" ? "本地模型" : "API 模式"}
                            </button>
                        ))}
                    </div>

                    {settings.embedding_mode === "local" ? (
                        <div>
                            <label className="text-xs text-gray-500 mb-1 block">模型路径</label>
                            <input
                                value={settings.embedding_model}
                                onChange={e => setSettings(s => s ? { ...s, embedding_model: e.target.value } : s)}
                                className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                           rounded text-sm text-gray-200 outline-none focus:border-indigo-500"
                            />
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <div>
                                <label className="text-xs text-gray-500 mb-1 block">API 地址</label>
                                <input
                                    value={settings.embedding_api_url}
                                    onChange={e => setSettings(s => s ? { ...s, embedding_api_url: e.target.value } : s)}
                                    placeholder="https://api.openai.com/v1"
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                             rounded text-sm text-gray-200 outline-none focus:border-indigo-500"
                                />
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 mb-1 block">API Key</label>
                                <input
                                    type="password"
                                    value={settings.embedding_api_key}
                                    onChange={e => setSettings(s => s ? { ...s, embedding_api_key: e.target.value } : s)}
                                    placeholder="sk-..."
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                             rounded text-sm text-gray-200 outline-none focus:border-indigo-500"
                                />
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 mb-1 block">模型名称</label>
                                <input
                                    value={settings.embedding_model}
                                    onChange={e => setSettings(s => s ? { ...s, embedding_model: e.target.value } : s)}
                                    placeholder="text-embedding-3-small"
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700
                             rounded text-sm text-gray-200 outline-none focus:border-indigo-500"
                                />
                            </div>
                        </div>
                    )}
                </div>
            </section>

            {/* 查询配置 */}
            <section className="mb-8">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-4">
                    查询配置
                </div>
                <div className="space-y-4 bg-gray-900 rounded-xl p-4 border border-gray-800">
                    <div>
                        <label className="text-xs text-gray-500 mb-1 block">
                            默认检索策略
                        </label>
                        <div className="flex gap-2 flex-wrap">
                            {["parallel", "sequential", "graph_augmented", "multi_hop"].map(s => (
                                <button
                                    key={s}
                                    onClick={() => setSettings(prev => prev ? { ...prev, query_strategy: s } : prev)}
                                    className={`px-3 py-1.5 rounded text-xs border transition-colors ${settings.query_strategy === s
                                            ? "bg-indigo-600 border-indigo-600 text-white"
                                            : "border-gray-700 text-gray-400 hover:border-gray-500"
                                        }`}
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <label className="text-xs text-gray-500 mb-2 block">
                            返回章节数量：{settings.query_top_k}
                        </label>
                        <input
                            type="range"
                            min="3"
                            max="10"
                            value={settings.query_top_k}
                            onChange={e => setSettings(s => s ? { ...s, query_top_k: e.target.value } : s)}
                            className="w-full accent-indigo-600"
                        />
                    </div>
                </div>
            </section>

            {/* 保存按钮 */}
            <button
                onClick={handleSave}
                disabled={saving}
                className="px-6 py-2 bg-indigo-600 text-white text-sm rounded-lg
                   hover:bg-indigo-500 disabled:opacity-40 transition-colors"
            >
                {saving ? "保存中..." : saved ? "已保存 ✓" : "保存设置"}
            </button>
        </div>
    );
}