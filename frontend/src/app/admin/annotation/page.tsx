"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { FileDown, Cpu } from "lucide-react";
import { SectionReviewer, type PendingSection } from "./SectionReviewer";
import { ImageReviewer, type PendingImage } from "./ImageReviewer";

interface PendingData {
    pending_sections: PendingSection[];
    pending_images: PendingImage[];
    total_pending: number;
}

export default function AnnotationPage() {
    const [data, setData]       = useState<PendingData | null>(null);
    const [loading, setLoading] = useState(true);
    const [tab, setTab]         = useState<"sections" | "images">("sections");
    const [secDone, setSecDone] = useState(0);
    const [imgDone, setImgDone] = useState(0);
    const [batchMsg, setBatchMsg] = useState("");

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetchApi<PendingData>("/api/annotation/pending");
            setData(res);
        } finally { setLoading(false); }
    }, []);

    useEffect(() => { load(); }, [load]);

    async function batchAnalyze() {
        setBatchMsg("启动批量分析...");
        try {
            const res = await fetchApi<{ count: number }>("/api/annotation/batch-analyze", { method: "POST" });
            setBatchMsg(`已启动 ${res.count} 张图片的后台分析，请稍后刷新`);
        } catch { setBatchMsg("启动失败"); }
    }

    async function exportCsv() {
        const token = localStorage.getItem("token") ?? "";
        const res = await fetch("/api/annotation/export-csv", { headers: { Authorization: `Bearer ${token}` } });
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a"); a.href = url; a.download = "pending_review.csv"; a.click();
        URL.revokeObjectURL(url);
    }

    const secTotal = data?.pending_sections.length ?? 0;
    const imgTotal = data?.pending_images.length ?? 0;
    const totalDone = secDone + imgDone;
    const totalAll  = secTotal + imgTotal;
    const pct = totalAll > 0 ? Math.round((totalDone / totalAll) * 100) : 0;

    return (
        <div className="p-6 max-w-5xl mx-auto">
            {/* Header */}
            <div className="flex items-start justify-between mb-6">
                <div>
                    <h1 className="text-xl font-semibold text-white">多模态手动补全</h1>
                    <p className="text-xs text-gray-500 mt-0.5">OCR 纠错 · 图片描述补充</p>
                </div>
                <div className="flex gap-2">
                    <button onClick={batchAnalyze}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-violet-600/20 border border-violet-500/30 text-violet-300 text-xs hover:bg-violet-600/30">
                        <Cpu size={12} />批量 VLM 分析
                    </button>
                    <button onClick={exportCsv}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-300 text-xs hover:text-white">
                        <FileDown size={12} />导出待审核
                    </button>
                </div>
            </div>

            {batchMsg && <div className="mb-4 px-4 py-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-xs text-violet-300">{batchMsg}</div>}

            {loading ? (
                <div className="text-gray-500 text-sm text-center py-12">加载中...</div>
            ) : (
                <>
                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-4 mb-6">
                        <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl">
                            <div className="text-2xl font-bold text-white">{secTotal}</div>
                            <div className="text-xs text-gray-500 mt-1">待审核章节</div>
                        </div>
                        <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl">
                            <div className="text-2xl font-bold text-white">{imgTotal}</div>
                            <div className="text-xs text-gray-500 mt-1">待审核图片</div>
                        </div>
                        <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl">
                            <div className="text-2xl font-bold text-white">{pct}%</div>
                            <div className="text-xs text-gray-500 mt-1">本次已完成 ({totalDone}/{totalAll})</div>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="flex gap-1 mb-4 bg-gray-900 border border-gray-800 rounded-lg p-1 w-fit">
                        <button onClick={() => setTab("sections")}
                            className={`px-4 py-1.5 rounded text-sm transition-colors ${tab === "sections" ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"}`}>
                            章节审核 ({secTotal})
                        </button>
                        <button onClick={() => setTab("images")}
                            className={`px-4 py-1.5 rounded text-sm transition-colors ${tab === "images" ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white"}`}>
                            图片审核 ({imgTotal})
                        </button>
                    </div>

                    {tab === "sections" && (
                        data?.pending_sections.length
                            ? <SectionReviewer sections={data.pending_sections} onProgress={setSecDone} />
                            : <div className="text-gray-500 text-sm py-8 text-center">暂无需审核的章节</div>
                    )}
                    {tab === "images" && (
                        data?.pending_images.length
                            ? <ImageReviewer images={data.pending_images} onProgress={setImgDone} />
                            : <div className="text-gray-500 text-sm py-8 text-center">暂无需审核的图片</div>
                    )}
                </>
            )}
        </div>
    );
}
