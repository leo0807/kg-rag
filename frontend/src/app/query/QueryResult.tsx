"use client";
import Link from "next/link";

interface SourceSection {
    chunk_id: string;
    doc_id: string;
    number: string;
    title: string;
    score: number;
}

interface Props {
    answer: string;
    sources: SourceSection[];
    streaming: boolean;
    rating: 1 | -1 | null;
    onFeedback: (r: 1 | -1) => void;
    onSourceClick?: (chunkId: string) => void;
}

export default function QueryResult({ answer, sources, streaming, rating, onFeedback, onSourceClick }: Props) {
    return (
        <>
            <div className="p-5 bg-gray-900 rounded-xl border border-gray-800 mb-4">
                <div className="flex items-center justify-between mb-3">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">回答</div>
                    {streaming && (
                        <div className="flex items-center gap-1.5">
                            <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse" />
                            <span className="text-xs text-indigo-400">生成中</span>
                        </div>
                    )}
                </div>
                <p className="text-gray-200 text-sm leading-relaxed whitespace-pre-wrap">
                    {answer}
                    {streaming && <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse" />}
                </p>
                {!streaming && (
                    <div className="flex items-center gap-3 mt-4 pt-4 border-t border-gray-700">
                        <span className="text-xs text-gray-500">这个回答有帮助吗？</span>
                        <button onClick={() => onFeedback(1)}
                            className={`px-3 py-1 rounded text-xs transition-colors ${rating === 1 ? "bg-green-600 text-white" : "bg-gray-800 text-gray-400 hover:text-green-400"
                                }`}>
                            👍 有帮助
                        </button>
                        <button onClick={() => onFeedback(-1)}
                            className={`px-3 py-1 rounded text-xs transition-colors ${rating === -1 ? "bg-red-600 text-white" : "bg-gray-800 text-gray-400 hover:text-red-400"
                                }`}>
                            👎 没帮助
                        </button>
                        {rating && <span className="text-xs text-gray-500">感谢反馈</span>}
                    </div>
                )}
            </div>

            {!streaming && sources.length > 0 && (
                <div>
                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
                        引用来源 · {sources.length} 个章节
                    </div>
                    <div className="space-y-2">
                        {sources.map(source => (
                            <Link
                                key={source.chunk_id}
                                href={`/library/${source.doc_id}`}
                                onClick={() => onSourceClick?.(source.chunk_id)}
                                className="flex items-center justify-between px-4 py-3
                           bg-gray-900 rounded-lg border border-gray-800
                           hover:border-indigo-500 transition-colors cursor-pointer">
                                <div>
                                    <span className="text-xs font-mono text-indigo-400 mr-2">
                                        {source.doc_id} §{source.number || source.chunk_id.split("_")[1]}
                                    </span>
                                    <span className="text-sm text-gray-300">{source.title}</span>
                                </div>
                                <span className="text-xs text-gray-600 flex-shrink-0 ml-4">
                                    {(source.score / 10).toFixed(2)}
                                </span>
                            </Link>
                        ))}
                    </div>
                </div>
            )}
        </>
    );
}