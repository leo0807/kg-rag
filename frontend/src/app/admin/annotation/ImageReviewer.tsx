"use client";
import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { RefreshCw } from "lucide-react";

export interface PendingImage {
    image_id: string; url: string | null; page_num: number; doc_id: string;
    current_caption: string; analysis_level: string;
}

interface Props {
    images: PendingImage[];
    onProgress: (done: number) => void;
}

export function ImageReviewer({ images, onProgress }: Props) {
    const [idx, setIdx]           = useState(0);
    const [caption, setCaption]   = useState("");
    const [isDrawing, setIsDrawing] = useState(false);
    const [saving, setSaving]     = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [doneCount, setDoneCount] = useState(0);

    const total = images.length;
    const current = images[idx];

    useEffect(() => {
        if (current) {
            setCaption(current.current_caption);
            setIsDrawing(false);
        }
    }, [current?.image_id]); // eslint-disable-line react-hooks/exhaustive-deps

    function advance(delta = 1) {
        const next = idx + delta;
        if (next >= 0 && next < total) { setIdx(next); }
    }

    async function save() {
        if (!current) return;
        setSaving(true);
        try {
            await fetchApi(`/api/annotation/images/${encodeURIComponent(current.image_id)}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ caption, is_drawing: isDrawing }),
            });
            const d = doneCount + 1; setDoneCount(d); onProgress(d);
            advance();
        } finally { setSaving(false); }
    }

    async function triggerVLM() {
        if (!current) return;
        setAnalyzing(true);
        try {
            await fetchApi(`/api/annotation/images/${encodeURIComponent(current.image_id)}/analyze`, { method: "POST" });
        } finally { setAnalyzing(false); }
    }

    if (!current) return <div className="text-gray-500 text-sm py-8 text-center">✅ 所有图片已审核完成</div>;

    const progress = Math.round((doneCount / total) * 100);

    return (
        <div className="space-y-4">
            {/* Progress */}
            <div className="flex items-center gap-3">
                <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 transition-all" style={{ width: `${progress}%` }} />
                </div>
                <span className="text-xs text-gray-500 whitespace-nowrap">已完成 {doneCount} / {total}</span>
            </div>

            {/* Card */}
            <div className="border border-gray-700 rounded-xl overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2.5 bg-gray-800/80 border-b border-gray-700">
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-indigo-400">{current.doc_id}</span>
                        <span className="text-xs text-gray-400">第 {current.page_num} 页</span>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-xs ${current.analysis_level === 'none' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'}`}>
                        {current.analysis_level === 'none' ? '未分析' : current.analysis_level}
                    </span>
                </div>
                <div className="grid grid-cols-2 divide-x divide-gray-700">
                    <div className="p-4 flex items-center justify-center bg-gray-950 min-h-[180px]">
                        {current.url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={current.url} alt="图片预览" className="max-h-52 max-w-full object-contain rounded" />
                        ) : (
                            <div className="text-gray-600 text-xs text-center">图片不可用<br/>{current.image_id}</div>
                        )}
                    </div>
                    <div className="p-4 flex flex-col gap-3">
                        <div className="flex-1">
                            <div className="text-xs text-gray-500 mb-1.5">图片描述</div>
                            <textarea value={caption} onChange={e => setCaption(e.target.value)} rows={6}
                                placeholder="输入图片描述..."
                                className="w-full px-2.5 py-1.5 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500 resize-none placeholder-gray-600" />
                        </div>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input type="checkbox" checked={isDrawing} onChange={e => setIsDrawing(e.target.checked)} className="accent-indigo-500" />
                            <span className="text-xs text-gray-400">这是工程图纸</span>
                        </label>
                        <button onClick={triggerVLM} disabled={analyzing}
                            className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded bg-violet-600/20 border border-violet-500/30 text-violet-300 text-xs hover:bg-violet-600/30 disabled:opacity-40">
                            <RefreshCw size={11} className={analyzing ? "animate-spin" : ""} />
                            {analyzing ? "分析中..." : "触发 VLM 分析"}
                        </button>
                    </div>
                </div>
                <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700 bg-gray-900/50">
                    <span className="text-xs text-gray-600">{idx + 1} / {total}</span>
                    <div className="flex gap-2">
                        <button onClick={() => advance()} className="px-3 py-1.5 rounded text-xs text-gray-500 hover:text-gray-300 hover:bg-gray-800">跳过</button>
                        <button onClick={save} disabled={saving || !caption.trim()}
                            className="px-4 py-1.5 rounded bg-indigo-600 text-white text-xs hover:bg-indigo-500 disabled:opacity-40">
                            {saving ? "保存中..." : "保存描述"}
                        </button>
                        <button onClick={() => advance()} className="px-3 py-1.5 rounded bg-gray-800 text-xs text-gray-300 hover:bg-gray-700">下一个 →</button>
                    </div>
                </div>
            </div>
        </div>
    );
}
