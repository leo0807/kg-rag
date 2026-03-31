"use client";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
    onBranch?: () => void;
}

export default function MessageBubble({ role, content, sources, images, streaming, onSourceClick, onBranch }: Props) {
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
                    {!streaming && onBranch && (
                        <button
                            onClick={onBranch}
                            className="ml-2 text-xs text-gray-600 hover:text-indigo-400 transition-colors flex items-center gap-1"
                            title="从此处开始新的分支对话"
                        >
                            <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M2 2v4a2 2 0 002 2h4M10 4l-2-2 2-2"/>
                            </svg>
                            分支
                        </button>
                    )}
                </div>

                {/* 回答内容 */}
                <div className="px-4 py-3 bg-gray-900 border border-gray-800 rounded-2xl rounded-tl-sm">
                    <div className="text-sm text-gray-200 leading-relaxed prose prose-invert prose-sm max-w-none
                                    prose-headings:text-gray-100 prose-headings:font-semibold
                                    prose-p:text-gray-200 prose-p:leading-relaxed
                                    prose-strong:text-gray-100
                                    prose-code:text-indigo-300 prose-code:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
                                    prose-pre:bg-gray-800 prose-pre:border prose-pre:border-gray-700 prose-pre:rounded-lg
                                    prose-li:text-gray-200
                                    prose-a:text-indigo-400 prose-a:no-underline hover:prose-a:underline
                                    prose-blockquote:border-indigo-500 prose-blockquote:text-gray-400
                                    prose-hr:border-gray-700
                                    prose-table:text-gray-200 prose-th:text-gray-100 prose-td:border-gray-700 prose-th:border-gray-700">
                        {streaming ? (
                            <>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                                <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse align-middle" />
                            </>
                        ) : (
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                        )}
                    </div>

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