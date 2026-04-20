"use client";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, ExternalLink, Reply, Star } from "lucide-react";
import { LLMErrorInfo, SourceSection } from "./types";
import SourceGraph from "./SourceGraph";

const RANK_COLORS = ["#fbbf24", "#34d399", "#60a5fa", "#f472b6", "#a78bfa"];

const ERROR_HINTS: Record<string, string> = {
    quota_exceeded:    "· 联系管理员充值或切换模型",
    rate_limited:      "· 稍等片刻后重试",
    timeout:           "· 点击重试，或换用响应更快的模型",
    service_unavailable: "· 检查 AI 服务是否正常运行",
    unknown_error:     "· 联系管理员查看后端日志",
};

interface Props {
    role: "user" | "assistant";
    content: string;
    sources?: SourceSection[];
    images?: string[];
    streaming?: boolean;
    followUpQuestions?: string[];
    errorInfo?: LLMErrorInfo;
    isAdmin?: boolean;
    onSourceClick?: (chunkId: string) => void;
    onQuoteSource?: (source: SourceSection) => void;
    onBranch?: () => void;
    onFollowUp?: (q: string) => void;
    onRetry?: () => void;
    onFavoriteSection?: (s: SourceSection) => void;
    favoritedChunkIds?: Set<string>;
}

export default function MessageBubble({
    role, content, sources, images, streaming,
    followUpQuestions, errorInfo, isAdmin,
    onSourceClick, onQuoteSource, onBranch, onFollowUp, onRetry,
    onFavoriteSection, favoritedChunkIds,
}: Props) {
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

                {/* 错误卡片 */}
                {errorInfo && (
                    <div className="px-4 py-3 bg-amber-950/40 border border-amber-600/70 rounded-2xl rounded-tl-sm">
                        <div className="flex items-start gap-2 mb-2">
                            <AlertTriangle size={15} className="text-amber-400 mt-0.5 shrink-0" />
                            <span className="text-sm font-medium text-amber-300">
                                {errorInfo.code === "quota_exceeded"      && "API 额度不足"}
                                {errorInfo.code === "rate_limited"        && "请求过于频繁"}
                                {errorInfo.code === "timeout"             && "模型响应超时"}
                                {errorInfo.code === "service_unavailable" && "AI 服务暂时不可用"}
                                {!["quota_exceeded","rate_limited","timeout","service_unavailable"].includes(errorInfo.code) && "AI 服务异常"}
                            </span>
                        </div>
                        <p className="text-xs text-amber-200/80 mb-3">{errorInfo.message}</p>

                        {isAdmin && (errorInfo.status_code || errorInfo.endpoint) && (
                            <div className="mb-3 px-3 py-2 bg-amber-900/30 border border-amber-700/40 rounded-lg text-xs text-amber-300/70 space-y-1">
                                <div className="font-medium text-amber-400 mb-1">管理员信息</div>
                                {errorInfo.status_code && <div>HTTP 状态码：<span className="font-mono">{errorInfo.status_code}</span></div>}
                                {errorInfo.endpoint   && <div>端点：<span className="font-mono break-all">{errorInfo.endpoint}</span></div>}
                                {errorInfo.code === "quota_exceeded" && (
                                    <div className="mt-1 space-y-0.5">
                                        <div>建议操作：</div>
                                        <div>· 充值：检查 API 提供商控制台</div>
                                        <div>· 或在 <span className="font-mono">.env</span> 设置 <span className="font-mono">LLM_MODE=local</span> 切换本地模型</div>
                                    </div>
                                )}
                            </div>
                        )}

                        <div className="text-xs text-amber-400/60 space-y-0.5">
                            <div className="font-medium mb-1">你可以：</div>
                            <div>{ERROR_HINTS[errorInfo.code] ?? ERROR_HINTS.unknown_error}</div>
                            {onRetry && (
                                <button
                                    onClick={onRetry}
                                    className="mt-2 px-3 py-1 text-xs bg-amber-800/40 hover:bg-amber-700/50
                                               border border-amber-600/50 rounded-lg text-amber-300 transition-colors"
                                >
                                    重试
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {/* 回答内容 */}
                {!errorInfo && <div className="px-4 py-3 bg-gray-900 border border-gray-800 rounded-2xl rounded-tl-sm">
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

                    {/* 追问建议 */}
                    {!streaming && followUpQuestions && followUpQuestions.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-gray-800 animate-fade-in">
                            <div className="text-xs text-gray-600 mb-2">追问建议</div>
                            <div className="flex flex-col gap-1.5">
                                {followUpQuestions.map((q, i) => (
                                    <button
                                        key={i}
                                        onClick={() => onFollowUp?.(q)}
                                        className="text-left px-3 py-1.5 text-xs text-indigo-300/80 bg-indigo-950/30
                                                   border border-indigo-800/40 rounded-lg hover:border-indigo-500/60
                                                   hover:text-indigo-200 hover:bg-indigo-950/50 transition-colors"
                                    >
                                        {q}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* 来源章节 */}
                    {!streaming && sources && sources.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-gray-800">
                            <div className="text-xs text-gray-600 mb-2">引用来源</div>
                            <div className="flex flex-wrap gap-2">
                                {sources.map((s, idx) => (
                                    <div key={s.chunk_id} className="inline-flex items-center group">
                                        {/* 引用按钮 */}
                                        <button
                                            onClick={() => {
                                                onSourceClick?.(s.chunk_id);
                                                onQuoteSource?.(s);
                                            }}
                                            title="点击追问此章节"
                                            className="inline-flex items-center gap-1.5 px-2.5 py-1
                                                       bg-gray-800 hover:bg-indigo-900/40 rounded-l-lg
                                                       border border-gray-700 hover:border-indigo-500
                                                       transition-colors"
                                        >
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
                                            <Reply size={10} className="text-gray-600 group-hover:text-indigo-400 transition-colors flex-shrink-0" />
                                        </button>
                                        {/* 跳转原文链接 */}
                                        <Link
                                            href={`/library/${s.doc_id}${s.page_idx !== undefined ? `?page=${s.page_idx}` : ""}`}
                                            title="查看原文并跳转锚点"
                                            className="px-1.5 py-1 border border-l-0 border-gray-700
                                                       hover:border-indigo-500
                                                       text-gray-600 hover:text-indigo-400 transition-colors"
                                        >
                                            <ExternalLink size={10} />
                                        </Link>
                                        {/* 收藏按钮 */}
                                        {onFavoriteSection && (
                                            <button
                                                onClick={() => onFavoriteSection(s)}
                                                title={favoritedChunkIds?.has(s.chunk_id) ? "取消收藏" : "收藏此章节"}
                                                className="px-1.5 py-1 border border-l-0 border-gray-700
                                                           hover:border-amber-500 rounded-r-lg
                                                           transition-colors"
                                            >
                                                <Star
                                                    size={10}
                                                    className={favoritedChunkIds?.has(s.chunk_id)
                                                        ? "text-amber-400 fill-amber-400"
                                                        : "text-gray-600 hover:text-amber-400"}
                                                />
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>
                            {/* 来源图谱 */}
                            <SourceGraph sources={sources} />
                        </div>
                    )}
                </div>}
            </div>
        </div>
    );
}