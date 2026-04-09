"use client";

import { useState, useEffect } from "react";
import { ModelSettings, getToken } from "./types";

interface Props {
    showMsg:   (m: string) => void;
    showError: (e: string) => void;
}

export function ModelTab({ showMsg, showError }: Props) {
    const [settings, setSettings] = useState<ModelSettings | null>(null);

    useEffect(() => {
        fetch("/api/settings/user", { headers: { Authorization: `Bearer ${getToken()}` } })
            .then(r => r.ok ? r.json() : null)
            .then(data => data && setSettings(data));
    }, []);

    async function save() {
        if (!settings) return;
        const res = await fetch("/api/settings/user", {
            method: "PUT",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${getToken()}` },
            body: JSON.stringify({ settings }),
        });
        if (res.ok) showMsg("设置已保存");
        else showError("保存失败");
    }

    if (!settings) return <div className="text-sm text-gray-500">加载中…</div>;

    return (
        <div className="space-y-6">
            <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-4">Embedding 模型</div>
                <div className="flex gap-2 mb-4">
                    {["local", "api"].map(mode => (
                        <button key={mode}
                            onClick={() => setSettings(s => s ? { ...s, embedding_mode: mode } : s)}
                            className={`px-3 py-1.5 rounded text-xs border transition-colors ${settings.embedding_mode === mode
                                ? "bg-indigo-600 border-indigo-600 text-white"
                                : "border-gray-700 text-gray-400 hover:border-gray-500"
                            }`}>
                            {mode === "local" ? "本地模型" : "API 模式"}
                        </button>
                    ))}
                </div>
                {settings.embedding_mode === "local" ? (
                    <div>
                        <label className="text-xs text-gray-500 mb-1 block">模型路径</label>
                        <input value={settings.embedding_model}
                            onChange={e => setSettings(s => s ? { ...s, embedding_model: e.target.value } : s)}
                            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                    </div>
                ) : (
                    <div className="space-y-3">
                        {[
                            { key: "embedding_api_url", label: "API 地址",  placeholder: "https://api.openai.com/v1" },
                            { key: "embedding_api_key", label: "API Key",   placeholder: "sk-..." },
                            { key: "embedding_model",   label: "模型名称", placeholder: "text-embedding-3-small" },
                        ].map(f => (
                            <div key={f.key}>
                                <label className="text-xs text-gray-500 mb-1 block">{f.label}</label>
                                <input value={settings[f.key as keyof ModelSettings]}
                                    onChange={e => setSettings(s => s ? { ...s, [f.key]: e.target.value } : s)}
                                    placeholder={f.placeholder}
                                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-4">查询配置</div>
                <div className="space-y-4">
                    <div>
                        <label className="text-xs text-gray-500 mb-2 block">默认检索策略</label>
                        <div className="flex gap-2 flex-wrap">
                            {["parallel", "sequential", "graph_augmented", "multi_hop"].map(s => (
                                <button key={s}
                                    onClick={() => setSettings(prev => prev ? { ...prev, query_strategy: s } : prev)}
                                    className={`px-3 py-1.5 rounded text-xs border transition-colors ${settings.query_strategy === s
                                        ? "bg-indigo-600 border-indigo-600 text-white"
                                        : "border-gray-700 text-gray-400 hover:border-gray-500"
                                    }`}>
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div>
                        <label className="text-xs text-gray-500 mb-2 block">
                            返回章节数量：{settings.query_top_k}
                        </label>
                        <input type="range" min="3" max="10"
                            value={settings.query_top_k}
                            onChange={e => setSettings(s => s ? { ...s, query_top_k: e.target.value } : s)}
                            className="w-full accent-indigo-600" />
                    </div>
                </div>
            </div>

            <button onClick={save}
                className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500">
                保存设置
            </button>
        </div>
    );
}
