"use client";

import { useState, useEffect } from "react";
import { Ruler, ImageOff, Loader2, Pencil } from "lucide-react";
import { DrawingViewer } from "./DrawingViewer";

interface Annotation {
    type: string; raw: string; parameter: string;
    value: string; value_max: string; value_min: string; unit: string;
}

interface DrawingImage {
    image_id:           string;
    caption:            string;
    path:               string;
    minio_path:         string | null;
    url:                string | null;
    description:        string;
    is_drawing:         boolean;
    part_numbers:       string[];
    annotations:        Annotation[];
    assembly_relations: string[];
    drawing_summary:    string;
    section_chunk_id:   string;
    section_number:     string;
    section_title:      string;
}

interface Props {
    docId: string;
}

export function DrawingsTab({ docId }: Props) {
    const [images,      setImages]      = useState<DrawingImage[]>([]);
    const [loading,     setLoading]     = useState(true);
    const [selected,    setSelected]    = useState<DrawingImage | null>(null);
    const [reanalyzing, setReanalyzing] = useState<string | null>(null);   // image_id being reanalyzed
    const [filter,      setFilter]      = useState<"all" | "drawing">("all");

    useEffect(() => {
        const token = localStorage.getItem("token") ?? "";
        fetch(`/api/documents/${docId}/images`, {
            headers: { Authorization: `Bearer ${token}` },
        })
            .then(r => r.json())
            .then(d => setImages(d.images ?? []))
            .catch(() => {})
            .finally(() => setLoading(false));
    }, [docId]);

    async function handleReanalyze(imageId: string) {
        setReanalyzing(imageId);
        const token = localStorage.getItem("token") ?? "";
        try {
            await fetch(`/api/documents/${docId}/images/${imageId}/analyze-drawing`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
            });
            // Poll after 8 s for updated result
            setTimeout(async () => {
                const r = await fetch(`/api/documents/${docId}/images`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                const d = await r.json();
                const updated = (d.images ?? []) as DrawingImage[];
                setImages(updated);
                // Refresh selected if still open
                setSelected(prev => prev
                    ? updated.find(img => img.image_id === prev.image_id) ?? prev
                    : null
                );
                setReanalyzing(null);
            }, 8000);
        } catch {
            setReanalyzing(null);
        }
    }

    // 只展示有真实 image_id 的图片（排除 Cypher OPTIONAL MATCH 返回的空行）
    const validImages = images.filter(img => !!img.image_id);
    const displayed = filter === "drawing"
        ? validImages.filter(img => img.is_drawing)
        : validImages;

    if (loading) {
        return (
            <div className="flex items-center justify-center py-16 text-gray-500 text-sm gap-2">
                <Loader2 size={16} className="animate-spin" />
                加载图片中...
            </div>
        );
    }

    if (validImages.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-gray-600 gap-3">
                <ImageOff size={32} strokeWidth={1.5} />
                <div className="text-sm">本文档暂无提取到的图片</div>
                <div className="text-xs text-gray-700">重新入库文档后图片将自动提取并分析</div>
            </div>
        );
    }

    return (
        <>
            {/* 过滤栏 */}
            <div className="flex items-center gap-2 mb-4">
                {(["all", "drawing"] as const).map(f => (
                    <button
                        key={f}
                        onClick={() => setFilter(f)}
                        className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                            filter === f
                                ? "bg-indigo-600 text-white"
                                : "text-gray-400 hover:text-white bg-gray-800 border border-gray-700"
                        }`}
                    >
                        {f === "all" ? `全部图片 (${validImages.length})` : `工程图纸 (${validImages.filter(i => i.is_drawing).length})`}
                    </button>
                ))}
            </div>

            {/* 图片网格 */}
            {displayed.length === 0 ? (
                <div className="text-center py-12 text-gray-600 text-sm">暂无工程图纸</div>
            ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {displayed.map((img, idx) => {
                        if (!img.image_id) return null;
                        const src = img.url ?? null;
                        return (
                            <button
                                key={img.image_id ?? idx}
                                onClick={() => setSelected(img)}
                                className="group relative bg-gray-900 border border-gray-800 rounded-xl
                                           overflow-hidden hover:border-indigo-500 transition-colors text-left"
                            >
                                <div className="aspect-[4/3] overflow-hidden bg-gray-800 flex items-center justify-center">
                                    {src ? (
                                        <img
                                            src={src}
                                            alt={img.caption || "图片"}
                                            className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-200"
                                            onError={e => {
                                                (e.currentTarget as HTMLImageElement).style.display = "none";
                                                (e.currentTarget.nextSibling as HTMLElement | null)?.removeAttribute("hidden");
                                            }}
                                        />
                                    ) : null}
                                    <span hidden={!!src} className="text-xs text-gray-600 px-3 text-center">图片暂不可用</span>
                                </div>
                                <div className="px-3 py-2">
                                    <div className="flex items-center gap-1.5 mb-0.5">
                                        {img.is_drawing && (
                                            <Ruler size={10} className="text-indigo-400 shrink-0" />
                                        )}
                                        <span className="text-xs text-gray-300 truncate">
                                            {img.caption || img.drawing_summary || "图片"}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-gray-600 font-mono">§{img.section_number}</span>
                                        <div className="flex items-center gap-1.5">
                                            {img.annotations.length > 0 && (
                                                <span className="text-xs text-indigo-400">
                                                    {img.annotations.length} 条标注
                                                </span>
                                            )}
                                            {reanalyzing === img.image_id && (
                                                <Loader2 size={10} className="animate-spin text-amber-400" />
                                            )}
                                        </div>
                                    </div>
                                </div>
                                {/* 无标注提示 */}
                                {!img.annotations.length && (
                                    <div className="absolute top-2 right-2 p-1 bg-gray-900/80 rounded"
                                         title="未提取到尺寸标注">
                                        <Pencil size={10} className="text-gray-500" />
                                    </div>
                                )}
                            </button>
                        );
                    })}
                </div>
            )}

            {/* 图纸详情弹窗 */}
            {selected && (
                <DrawingViewer
                    image={selected}
                    onClose={() => setSelected(null)}
                    onReanalyze={handleReanalyze}
                    reanalyzing={reanalyzing === selected.image_id}
                />
            )}
        </>
    );
}
