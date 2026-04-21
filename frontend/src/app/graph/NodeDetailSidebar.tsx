"use client";

import { useState, useEffect, useRef } from "react";
import { X, ZoomIn, ZoomOut, MessageSquarePlus, Trash2, Loader2, Image as ImageIcon } from "lucide-react";
import { GraphNode, NODE_COLOR } from "./constants";
import { fetchApi } from "@/lib/api";

interface Annotation {
    id:         number;
    node_id:    string;
    node_type:  string;
    user_id:    string;
    username:   string;
    full_name:  string;
    content:    string;
    created_at: string;
    updated_at: string;
}

interface ImageDetail {
    image_id:        string;
    doc_id:          string | null;
    caption:         string | null;
    description:     string | null;
    is_drawing:      boolean;
    drawing_summary: string | null;
    keywords:        string | null;
    page:            number | null;
    section_chunk_id: string | null;
    section_number:  string | null;
    section_title:   string | null;
    url:             string | null;
    analyzed:        boolean;
}

interface Props {
    node:           GraphNode;
    onClose:        () => void;
    onExpandSection?: (chunkId: string) => void;
    expandingId?:   string | null;
}

export function NodeDetailSidebar({ node, onClose, onExpandSection, expandingId }: Props) {
    const type    = node.type || node.label;
    const color   = NODE_COLOR[type] ?? "#6b7280";
    const isImage = type === "Image";

    // Image 节点：使用代理 URL，支持放大
    const imgUrl  = isImage ? (node.url || null) : null;
    const [imgOpen, setImgOpen]         = useState(false);
    const [zoom,    setZoom]            = useState(1);

    // Image 详情（含所属章节）
    const [imgDetail, setImgDetail]     = useState<ImageDetail | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);
    useEffect(() => {
        if (!isImage) return;
        let cancelled = false;
        setDetailLoading(true);
        fetchApi<ImageDetail>(`/api/images/${encodeURIComponent(node.id)}/detail`)
            .then(d => { if (!cancelled) setImgDetail(d); })
            .catch(() => {})
            .finally(() => { if (!cancelled) setDetailLoading(false); });
        return () => { cancelled = true; };
    }, [node.id, isImage]);

    // ── 批注状态 ──────────────────────────────────────────────────────────
    // node.id 对所有节点类型均为唯一标识（Section 的 id 即 chunk_id）
    const nodeId = node.id;
    const [annotations, setAnnotations] = useState<Annotation[]>([]);
    const [annLoading,  setAnnLoading]  = useState(false);
    const [draft,       setDraft]       = useState("");
    const [submitting,  setSubmitting]  = useState(false);
    const [annError,    setAnnError]    = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // 当前登录用户 id（用于判断是否可删除）
    const currentUserId: string = (() => {
        try {
            const u = JSON.parse(localStorage.getItem("user") ?? "{}");
            return u.id ?? "";
        } catch { return ""; }
    })();
    const isAdmin: boolean = (() => {
        try {
            const u = JSON.parse(localStorage.getItem("user") ?? "{}");
            return u.is_admin ?? false;
        } catch { return false; }
    })();

    useEffect(() => {
        let cancelled = false;
        async function load() {
            setAnnLoading(true);
            setAnnError("");
            try {
                const data = await fetchApi<Annotation[]>(`/api/annotations/${encodeURIComponent(nodeId)}`);
                if (!cancelled) setAnnotations(data);
            } catch {
                if (!cancelled) setAnnError("批注加载失败");
            } finally {
                if (!cancelled) setAnnLoading(false);
            }
        }
        load();
        return () => { cancelled = true; };
    }, [nodeId]);

    async function handleSubmit() {
        if (!draft.trim() || submitting) return;
        setSubmitting(true);
        setAnnError("");
        try {
            const ann = await fetchApi<Annotation>("/api/annotations", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ node_id: nodeId, node_type: type, content: draft.trim() }),
            });
            setAnnotations(prev => [...prev, ann]);
            setDraft("");
        } catch (e: unknown) {
            setAnnError(e instanceof Error ? e.message : "提交失败");
        } finally {
            setSubmitting(false);
        }
    }

    async function handleDelete(id: number) {
        try {
            await fetchApi(`/api/annotations/${id}`, { method: "DELETE" });
            setAnnotations(prev => prev.filter(a => a.id !== id));
        } catch (e: unknown) {
            setAnnError(e instanceof Error ? e.message : "删除失败");
        }
    }

    return (
        <div className="w-72 shrink-0 bg-gray-900 border-l border-gray-700 flex flex-col overflow-auto">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
                <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ backgroundColor: color + "33", color }}>
                    {type}
                </span>
                <button onClick={onClose} className="p-1 rounded hover:bg-gray-800 text-gray-500 hover:text-gray-100 transition-colors">
                    <X size={14} />
                </button>
            </div>

            <div className="px-4 py-3 border-b border-gray-800">
                <div className="text-sm font-semibold text-gray-100 leading-snug">{node.name || node.id}</div>
                {node.doc_id && <div className="text-xs text-gray-500 font-mono mt-1">{node.doc_id}</div>}
            </div>

            {/* ── Image 专属区域 ─────────────────────────────────────── */}
            {isImage && (
                <>
                    {/* 图片主体 */}
                    <div className="px-4 py-3 border-b border-gray-800 bg-gray-950">
                        {detailLoading && !imgUrl && (
                            <div className="flex justify-center py-6">
                                <Loader2 size={18} className="animate-spin text-gray-600" />
                            </div>
                        )}
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
                        {!imgUrl && !detailLoading && (
                            <div className="flex flex-col items-center gap-1 py-4 text-gray-700">
                                <ImageIcon size={24} />
                                <span className="text-[11px]">图片不可用</span>
                            </div>
                        )}
                    </div>

                    {/* 元数据区 */}
                    <div className="px-4 py-3 border-b border-gray-800 space-y-2">
                        {/* is_drawing 标签 */}
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-600 w-20 shrink-0">类型</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                (imgDetail?.is_drawing ?? node.is_drawing)
                                    ? "bg-indigo-900/60 text-indigo-300"
                                    : "bg-gray-800 text-gray-400"
                            }`}>
                                {(imgDetail?.is_drawing ?? node.is_drawing) ? "工程图纸" : "普通图片"}
                            </span>
                        </div>

                        {/* 分析状态 */}
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-600 w-20 shrink-0">分析状态</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                imgDetail?.analyzed
                                    ? "bg-emerald-900/60 text-emerald-300"
                                    : "bg-gray-800 text-gray-500"
                            }`}>
                                {detailLoading ? "加载中…" : imgDetail?.analyzed ? "已分析" : "待分析"}
                            </span>
                        </div>

                        {/* 所属文档 */}
                        {(imgDetail?.doc_id ?? node.doc_id) && (
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-600 w-20 shrink-0">所属文档</span>
                                <span className="text-xs text-gray-300 font-mono">
                                    {imgDetail?.doc_id ?? node.doc_id}
                                </span>
                            </div>
                        )}

                        {/* 所属章节 */}
                        {imgDetail?.section_title && (
                            <div className="flex items-start gap-2">
                                <span className="text-xs text-gray-600 w-20 shrink-0 mt-0.5">所属章节</span>
                                <span className="text-xs text-gray-300 leading-snug">
                                    {imgDetail.section_number && (
                                        <span className="font-mono text-amber-400 mr-1">{imgDetail.section_number}</span>
                                    )}
                                    {imgDetail.section_title}
                                </span>
                            </div>
                        )}

                        {/* 页码 */}
                        {(imgDetail?.page ?? null) !== null && (
                            <div className="flex items-center gap-2">
                                <span className="text-xs text-gray-600 w-20 shrink-0">页码</span>
                                <span className="text-xs text-gray-400">第 {imgDetail!.page} 页</span>
                            </div>
                        )}
                    </div>

                    {/* caption */}
                    {(imgDetail?.caption ?? node.name) && (
                        <div className="px-4 py-3 border-b border-gray-800">
                            <div className="text-xs text-gray-500 mb-1">Caption</div>
                            <p className="text-xs text-gray-300 leading-relaxed">
                                {imgDetail?.caption ?? node.name}
                            </p>
                        </div>
                    )}

                    {/* VLM 描述 */}
                    {(imgDetail?.description ?? node.description) && (
                        <div className="px-4 py-3 border-b border-gray-800">
                            <div className="text-xs text-gray-500 mb-1">VLM 分析</div>
                            <p className="text-xs text-gray-300 leading-relaxed">
                                {imgDetail?.description ?? node.description}
                            </p>
                        </div>
                    )}

                    {/* 图纸摘要 */}
                    {imgDetail?.drawing_summary && (
                        <div className="px-4 py-3 border-b border-gray-800">
                            <div className="text-xs text-gray-500 mb-1">图纸摘要</div>
                            <p className="text-xs text-gray-300 leading-relaxed">{imgDetail.drawing_summary}</p>
                        </div>
                    )}
                </>
            )}

            {/* ── 非 Image 节点的通用描述 ─────────────────────────────── */}
            {!isImage && node.description && (
                <div className="px-4 py-3 border-b border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">VLM 分析</div>
                    <p className="text-xs text-gray-300 leading-relaxed">{node.description}</p>
                </div>
            )}

            {!isImage && (
                <div className="px-4 py-3 space-y-2 border-b border-gray-800">
                    {Object.entries(node)
                        .filter(([k]) => !["id","name","label","type","x","y","fx","fy","description","path","url","content","chunk_id"].includes(k))
                        .map(([k, v]) => v != null && String(v) !== "" && (
                            <div key={k} className="flex gap-2">
                                <span className="text-xs text-gray-600 w-20 shrink-0">{k}</span>
                                <span className="text-xs text-gray-300 break-all">{String(v)}</span>
                            </div>
                        ))}
                </div>
            )}

            {/* ── 批注区 ──────────────────────────────────────────────── */}
            <div className="px-4 py-3 flex flex-col gap-2 flex-1">
                <div className="flex items-center gap-1.5 text-xs text-gray-400 font-medium">
                    <MessageSquarePlus size={13} />
                    现场批注
                    {annotations.length > 0 && (
                        <span className="ml-auto text-gray-600">{annotations.length} 条</span>
                    )}
                </div>

                {annLoading && (
                    <div className="flex justify-center py-4">
                        <Loader2 size={16} className="animate-spin text-gray-600" />
                    </div>
                )}

                {!annLoading && annotations.length === 0 && (
                    <p className="text-[11px] text-gray-600 text-center py-2">暂无批注</p>
                )}

                {!annLoading && annotations.map(a => (
                    <div key={a.id} className="bg-gray-800/60 rounded-lg px-3 py-2 text-xs group relative">
                        <div className="flex items-center gap-1.5 text-gray-500 mb-1">
                            <span className="text-indigo-400 font-medium">{a.full_name}</span>
                            <span>·</span>
                            <span>{new Date(a.created_at).toLocaleDateString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                        </div>
                        <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">{a.content}</p>
                        {(a.user_id === currentUserId || isAdmin) && (
                            <button
                                onClick={() => handleDelete(a.id)}
                                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded text-gray-600 hover:text-red-400 transition-all"
                                title="删除批注"
                            >
                                <Trash2 size={11} />
                            </button>
                        )}
                    </div>
                ))}

                {annError && (
                    <p className="text-[11px] text-red-400 text-center">{annError}</p>
                )}

                {/* 输入框 */}
                <div className="mt-auto pt-2">
                    <textarea
                        ref={textareaRef}
                        value={draft}
                        onChange={e => setDraft(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit();
                        }}
                        placeholder="添加现场心得或纠错备注… (Ctrl+Enter 提交)"
                        rows={3}
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-xs
                                   text-gray-200 placeholder-gray-600 outline-none focus:border-indigo-500
                                   resize-none leading-relaxed"
                    />
                    <button
                        onClick={handleSubmit}
                        disabled={!draft.trim() || submitting}
                        className="mt-1.5 w-full py-1.5 rounded-lg text-xs font-medium transition-colors
                                   bg-indigo-600 hover:bg-indigo-500 text-white
                                   disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                        {submitting ? "提交中…" : "提交批注"}
                    </button>
                </div>
            </div>

            {type === "Section" && node.has_children && onExpandSection && (
                <div className="px-4 pb-3">
                    <button
                        onClick={() => onExpandSection(node.id)}
                        disabled={expandingId === node.id}
                        className="w-full flex items-center justify-center gap-1.5 px-3 py-2
                                   bg-amber-600/20 hover:bg-amber-600/40 border border-amber-600/40
                                   text-amber-300 text-xs rounded-lg transition-colors disabled:opacity-50"
                    >
                        {expandingId === node.id ? "加载子节点…" : "展开子章节"}
                    </button>
                </div>
            )}

            {type === "Document" && (
                <div className="px-4 pb-4">
                    <a href={`/library/${node.doc_id || node.id}`}
                        className="block w-full text-center px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded-lg transition-colors">
                        查看文档
                    </a>
                </div>
            )}

            {imgOpen && imgUrl && (
                <div className="fixed inset-0 z-[200] bg-black/80 flex items-center justify-center"
                    onClick={() => setImgOpen(false)}>
                    <div className="relative max-w-[90vw] max-h-[90vh]"
                        onClick={e => e.stopPropagation()}>
                        <div className="absolute -top-10 right-0 flex items-center gap-2">
                            <button
                                onClick={() => setZoom(z => Math.max(0.25, +(z - 0.25).toFixed(2)))}
                                className="w-8 h-8 rounded bg-gray-900/80 text-gray-200 hover:text-gray-100 border border-gray-700 flex items-center justify-center"
                                title="缩小"
                            >
                                <ZoomOut size={14} />
                            </button>
                            <div className="text-xs text-gray-300 w-12 text-center">{Math.round(zoom * 100)}%</div>
                            <button
                                onClick={() => setZoom(z => Math.min(4, +(z + 0.25).toFixed(2)))}
                                className="w-8 h-8 rounded bg-gray-900/80 text-gray-200 hover:text-gray-100 border border-gray-700 flex items-center justify-center"
                                title="放大"
                            >
                                <ZoomIn size={14} />
                            </button>
                            <button
                                onClick={() => setImgOpen(false)}
                                className="ml-2 w-8 h-8 rounded bg-gray-900/80 text-gray-200 hover:text-gray-100 border border-gray-700 flex items-center justify-center"
                                title="关闭"
                            >
                                <X size={14} />
                            </button>
                        </div>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src={imgUrl}
                            alt={node.name}
                            className="block max-w-[90vw] max-h-[90vh] object-contain"
                            style={{ transform: `scale(${zoom})`, transformOrigin: "center center" }}
                        />
                    </div>
                </div>
            )}
        </div>
    );
}
