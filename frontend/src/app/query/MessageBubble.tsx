"use client";
import Link from "next/link";
import { SourceSection } from "./types";
import SourceGraph from "./SourceGraph";

const RANK_COLORS = ["#fbbf24", "#34d399", "#60a5fa", "#f472b6", "#a78bfa"];

interface Props {
    role: "user" | "assistant";
    content: string;
    sources?: SourceSection[];
    images?: string[];
    streaming?: boolean;
    onSourceClick?: (chunkId: string) => void;
}

export default function MessageBubble({ role, content, sources, images, streaming, onSourceClick }: Props) {
    if (role === "user") {
        return (
            <div className="flex justify-end mb-6">
                <div className="max-w-[75%] flex flex-col items-end gap-2">
                    {images && images.length > 0 && (
                        <div className="flex flex-wrap gap-2 justify-end">
                            {images.map((src, i) => (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img key={i} src={src} alt=""
                                    className="max-h-48 max-w-xs rounded-xl border border-indigo-500/30 object-contain bg-gray-900" />
                            ))}
                        </div>
                    )}
                    {content && (
                        <div className="px-4 py-3 bg-indigo-600 rounded-2xl rounded-tr-sm">
                            <p className="text-sm text-white leading-relaxed whitespace-pre-wrap">{content}</p>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    return (
        <div className="flex justify-start mb-6">
            <div className="max-w-[85%] w-full">
                {/* AI 头像 */}
                <div className="flex items-center gap-2 mb-2">
                    <div className="w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/30
                          flex items-center justify-center text-xs text-indigo-400 font-bold">
                        AI
                    </div>
                    <span className="text-xs text-gray-600">CPS 知识库</span>
                    {streaming && (
                        <div className="flex items-center gap-1 ml-1">
                            <div className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                            <div className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                            <div className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                    )}
                </div>

                {/* 回答内容 */}
                <div className="px-4 py-3 bg-gray-900 border border-gray-800 rounded-2xl rounded-tl-sm">
                    <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
                        {content}
                        {streaming && <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse align-middle" />}
                    </p>

                    {/* 来源章节 */}
                    {!streaming && sources && sources.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-gray-800">
                            <div className="text-xs text-gray-600 mb-2">引用来源</div>
                            <div className="flex flex-wrap gap-2">
                                {sources.map((s, idx) => (
                                    <Link
                                        key={s.chunk_id}
                                        href={`/library/${s.doc_id}`}
                                        onClick={() => onSourceClick?.(s.chunk_id)}
                                        className="inline-flex items-center gap-1.5 px-2.5 py-1
                               bg-gray-800 hover:bg-gray-700 rounded-lg
                               border border-gray-700 hover:border-indigo-500
                               transition-colors cursor-pointer"
                                    >
                                        {/* 排名徽章 */}
                                        <span className="w-4 h-4 rounded-full flex items-center justify-center
                                                         text-[10px] font-bold text-gray-900 flex-shrink-0"
                                              style={{ backgroundColor: RANK_COLORS[idx] ?? "#6b7280" }}>
                                            {idx + 1}
                                        </span>
                                        <span className="text-xs font-mono text-indigo-400">
                                            {s.doc_id} §{s.number}
                                        </span>
                                        <span className="text-xs text-gray-400 max-w-[120px] truncate">
                                            {s.title}
                                        </span>
                                    </Link>
                                ))}
                            </div>
                            {/* 来源图谱 */}
                            <SourceGraph sources={sources} />
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}