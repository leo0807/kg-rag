"use client";

import { useEffect, useState } from "react";
import { Image as ImageIcon, Loader2, X, ZoomIn, ZoomOut } from "lucide-react";
import { fetchApi } from "@/lib/api";
import type { GraphNode } from "./constants";

interface ImageDetail {
    image_id:         string;
    doc_id:           string | null;
    caption:          string | null;
    description:      string | null;
    is_drawing:       boolean;
    drawing_summary:  string | null;
    keywords:         string | null;
    page:             number | null;
    section_chunk_id: string | null;
    section_number:   string | null;
    section_title:    string | null;
    url:              string | null;
    analyzed:         boolean;
}

interface Props { node: GraphNode; }

export function ImageNodeDetail({ node }: Props) {
    const imgUrl = node.url || null;
    const [imgOpen, setImgOpen]         = useState(false);
    const [zoom,    setZoom]            = useState(1);
    const [detail,  setDetail]          = useState<ImageDetail | null>(null);
    const [loading, setLoading]         = useState(false);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        fetchApi<ImageDetail>(`/api/images/${encodeURIComponent(node.id)}/detail`)
            .then(d => { if (!cancelled) setDetail(d); })
            .catch(() => {})
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
    }, [node.id]);

    return (
        <>
            {/* Image preview */}
            <div className="px-4 py-3 border-b border-gray-800 bg-gray-950">
                {loading && !imgUrl && <div className="flex justify-center py-6"><Loader2 size={18} className="animate-spin text-gray-600" /></div>}
                {imgUrl && (
                    <>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={imgUrl} alt={node.name}
                            className="max-w-full w-full object-contain rounded-lg cursor-zoom-in"
                            style={{ maxWidth: 400 }}
                            onClick={() => { setZoom(1); setImgOpen(true); }}
                            onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
                        <div className="mt-2 text-[11px] text-gray-500">点击图片可放大</div>
                    </>
                )}
                {!imgUrl && !loading && (
                    <div className="flex flex-col items-center gap-1 py-4 text-gray-700">
                        <ImageIcon size={24} />
                        <span className="text-[11px]">图片不可用</span>
                    </div>
                )}
            </div>

            {/* Metadata */}
            <div className="px-4 py-3 border-b border-gray-800 space-y-2">
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-600 w-20 shrink-0">类型</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        (detail?.is_drawing ?? node.is_drawing) ? "bg-indigo-900/60 text-indigo-300" : "bg-gray-800 text-gray-400"
                    }`}>
                        {(detail?.is_drawing ?? node.is_drawing) ? "工程图纸" : "普通图片"}
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-600 w-20 shrink-0">分析状态</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        detail?.analyzed ? "bg-emerald-900/60 text-emerald-300" : "bg-gray-800 text-gray-500"
                    }`}>
                        {loading ? "加载中…" : detail?.analyzed ? "已分析" : "待分析"}
                    </span>
                </div>
                {(detail?.doc_id ?? node.doc_id) && (
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-600 w-20 shrink-0">所属文档</span>
                        <span className="text-xs text-gray-300 font-mono">{detail?.doc_id ?? node.doc_id}</span>
                    </div>
                )}
                {detail?.section_title && (
                    <div className="flex items-start gap-2">
                        <span className="text-xs text-gray-600 w-20 shrink-0 mt-0.5">所属章节</span>
                        <span className="text-xs text-gray-300 leading-snug">
                            {detail.section_number && <span className="font-mono text-amber-400 mr-1">{detail.section_number}</span>}
                            {detail.section_title}
                        </span>
                    </div>
                )}
                {(detail?.page ?? null) !== null && (
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-600 w-20 shrink-0">页码</span>
                        <span className="text-xs text-gray-400">第 {detail!.page} 页</span>
                    </div>
                )}
            </div>

            {(detail?.caption ?? node.name) && (
                <div className="px-4 py-3 border-b border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">Caption</div>
                    <p className="text-xs text-gray-300 leading-relaxed">{detail?.caption ?? node.name}</p>
                </div>
            )}
            {(detail?.description ?? node.description) && (
                <div className="px-4 py-3 border-b border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">VLM 分析</div>
                    <p className="text-xs text-gray-300 leading-relaxed">{detail?.description ?? node.description}</p>
                </div>
            )}
            {detail?.drawing_summary && (
                <div className="px-4 py-3 border-b border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">图纸摘要</div>
                    <p className="text-xs text-gray-300 leading-relaxed">{detail.drawing_summary}</p>
                </div>
            )}

            {/* Lightbox */}
            {imgOpen && imgUrl && (
                <div className="fixed inset-0 z-[200] bg-black/80 flex items-center justify-center" onClick={() => setImgOpen(false)}>
                    <div className="relative max-w-[90vw] max-h-[90vh]" onClick={e => e.stopPropagation()}>
                        <div className="absolute -top-10 right-0 flex items-center gap-2">
                            <button onClick={() => setZoom(z => Math.max(0.25, +(z - 0.25).toFixed(2)))}
                                className="w-8 h-8 rounded bg-gray-900/80 text-gray-200 hover:text-gray-100 border border-gray-700 flex items-center justify-center" title="缩小">
                                <ZoomOut size={14} />
                            </button>
                            <div className="text-xs text-gray-300 w-12 text-center">{Math.round(zoom * 100)}%</div>
                            <button onClick={() => setZoom(z => Math.min(4, +(z + 0.25).toFixed(2)))}
                                className="w-8 h-8 rounded bg-gray-900/80 text-gray-200 hover:text-gray-100 border border-gray-700 flex items-center justify-center" title="放大">
                                <ZoomIn size={14} />
                            </button>
                            <button onClick={() => setImgOpen(false)}
                                className="ml-2 w-8 h-8 rounded bg-gray-900/80 text-gray-200 hover:text-gray-100 border border-gray-700 flex items-center justify-center" title="关闭">
                                <X size={14} />
                            </button>
                        </div>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={imgUrl} alt={node.name}
                            className="block max-w-[90vw] max-h-[90vh] object-contain"
                            style={{ transform: `scale(${zoom})`, transformOrigin: "center center" }} />
                    </div>
                </div>
            )}
        </>
    );
}
