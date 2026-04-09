"use client";

import { Compass, ChevronLeft, ChevronRight, Square, X } from "lucide-react";
import { TourStop, NODE_COLOR } from "./constants";

interface Props {
    tourTopic:     string;
    setTourTopic:  (v: string) => void;
    tourRunning:   boolean;
    tourStops:     TourStop[];
    tourIdx:       number;
    tourTotal:     number;
    tourText:      string;
    tourStreaming:  boolean;
    hasPrev:       boolean;
    hasNext:       boolean;
    onStart:       () => void;
    onStop:        () => void;
    onNavigate:    (idx: number) => void;
    onClose:       () => void;
}

export function TourPanel({
    tourTopic, setTourTopic, tourRunning, tourStops, tourIdx, tourTotal,
    tourText, tourStreaming, hasPrev, hasNext,
    onStart, onStop, onNavigate, onClose,
}: Props) {
    const showInput = !tourRunning && tourStops.length === 0;

    return (
        <div className="shrink-0 border-t border-gray-800 bg-gray-900">
            {showInput ? (
                <div className="flex items-center gap-3 px-4 py-3">
                    <Compass size={15} className="text-amber-400 shrink-0" />
                    <input
                        value={tourTopic}
                        onChange={e => setTourTopic(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && onStart()}
                        placeholder="输入导览主题，如：液压系统安装、密封件更换…"
                        className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg
                                   text-sm text-gray-200 placeholder-gray-600
                                   outline-none focus:border-amber-500 transition-colors"
                    />
                    <button onClick={onStart} disabled={!tourTopic.trim()}
                        className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-gray-950
                                   text-sm font-medium rounded-lg transition-colors
                                   disabled:opacity-40 disabled:cursor-not-allowed">
                        开始漫游
                    </button>
                    <button onClick={onClose} className="p-1.5 text-gray-600 hover:text-white transition-colors">
                        <X size={14} />
                    </button>
                </div>
            ) : (
                <div className="flex flex-col px-4 py-3 gap-2.5" style={{ minHeight: 140 }}>
                    {/* Top control bar */}
                    <div className="flex items-center gap-2 shrink-0">
                        <Compass size={14} className="text-amber-400 shrink-0" />
                        <span className="text-xs text-amber-300 font-medium truncate max-w-[200px]">
                            「{tourTopic}」
                        </span>
                        <div className="flex items-center gap-1 mx-2">
                            {Array.from({ length: tourTotal || tourStops.length }).map((_, i) => (
                                <button key={i} onClick={() => onNavigate(i)} disabled={i >= tourStops.length}
                                    className={`rounded-full transition-all ${
                                        i === tourIdx       ? "w-3.5 h-3.5 bg-amber-400"           :
                                        i < tourStops.length ? "w-2 h-2 bg-gray-500 hover:bg-gray-300" :
                                                              "w-2 h-2 bg-gray-800"
                                    }`}
                                    title={tourStops[i]?.node.name}
                                />
                            ))}
                            {tourRunning && <span className="text-xs text-gray-600 ml-1 animate-pulse">…</span>}
                        </div>
                        <div className="ml-auto flex items-center gap-1">
                            <button onClick={() => onNavigate(tourIdx - 1)} disabled={!hasPrev}
                                className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors">
                                <ChevronLeft size={14} />
                            </button>
                            <span className="text-xs text-gray-600 w-12 text-center">{tourIdx + 1} / {tourTotal || "?"}</span>
                            <button onClick={() => onNavigate(tourIdx + 1)} disabled={!hasNext}
                                className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors">
                                <ChevronRight size={14} />
                            </button>
                            <button onClick={onStop}
                                className="flex items-center gap-1 px-2 py-1 ml-1 rounded bg-gray-800 text-red-400 hover:text-white text-xs transition-colors">
                                <Square size={10} />停止
                            </button>
                        </div>
                    </div>

                    {/* Current node + explanation */}
                    {tourIdx >= 0 && tourStops[tourIdx] && (
                        <div className="flex items-start gap-3 flex-1 min-h-0">
                            <div className="shrink-0 mt-0.5">
                                <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium"
                                    style={{
                                        backgroundColor: (NODE_COLOR[tourStops[tourIdx].node.type || ""] ?? "#6b7280") + "33",
                                        color:            NODE_COLOR[tourStops[tourIdx].node.type || ""] ?? "#9ca3af",
                                    }}>
                                    {tourStops[tourIdx].node.type}
                                </span>
                            </div>
                            <div className="flex-1 min-w-0 overflow-auto" style={{ maxHeight: 90 }}>
                                <div className="text-sm font-semibold text-white leading-tight mb-1 truncate">
                                    {tourStops[tourIdx].node.name}
                                </div>
                                <div className="text-xs text-gray-300 leading-relaxed">
                                    {tourText || (tourStreaming ? "" : "—")}
                                    {tourStreaming && (
                                        <span className="inline-block w-0.5 h-3.5 bg-amber-400 ml-0.5 align-middle animate-pulse" />
                                    )}
                                </div>
                            </div>
                            {tourStops[tourIdx].node.doc_id && (
                                <div className="shrink-0 text-xs text-gray-600 font-mono mt-0.5">
                                    {tourStops[tourIdx].node.doc_id}
                                </div>
                            )}
                        </div>
                    )}

                    {tourRunning && tourIdx < 0 && (
                        <div className="flex items-center gap-2 text-xs text-gray-500 animate-pulse">
                            <Compass size={12} className="text-amber-400" />
                            AI 正在规划导览路径…
                        </div>
                    )}

                    {!tourRunning && tourStops.length > 0 && (
                        <div className="text-xs text-gray-600 mt-auto shrink-0">
                            导览完成，共 {tourStops.length} 站 ·{" "}
                            <button onClick={() => { onStop(); setTourTopic(""); }}
                                className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2">
                                重新开始
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
