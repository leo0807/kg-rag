"use client";

import Link from "next/link";
import { X } from "lucide-react";
import type { RefNode } from "./useReferences";

interface Props {
    selected: RefNode;
    outNeighbors: string[];
    inNeighbors: string[];
    onClose: () => void;
    onFocus: (id: string) => void;
}

export function ReferenceDetailPanel({ selected, outNeighbors, inNeighbors, onClose, onFocus }: Props) {
    return (
        <div className="w-60 shrink-0 border-l border-gray-800 bg-gray-900 overflow-y-auto flex flex-col">
            <div className="px-4 py-4 border-b border-gray-800 flex items-start justify-between gap-2">
                <div>
                    <div className="text-sm font-bold text-white font-mono">{selected.id}</div>
                    <div className="text-xs text-gray-400 mt-0.5 leading-relaxed">{selected.title}</div>
                </div>
                <button onClick={onClose} className="text-gray-600 hover:text-white mt-0.5">
                    <X size={14} />
                </button>
            </div>

            <div className="px-4 py-3 border-b border-gray-800">
                <div className="text-xs text-gray-500 mb-2">
                    引用了 <span className="text-gray-300">{outNeighbors.length}</span> 份文档
                </div>
                {outNeighbors.length === 0
                    ? <p className="text-xs text-gray-600">—</p>
                    : <div className="space-y-1">
                        {outNeighbors.map(id => (
                            <button key={id} onClick={() => onFocus(id)}
                                className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                                <span className="text-gray-600">→</span>
                                <span className="font-mono">{id}</span>
                            </button>
                        ))}
                    </div>
                }
            </div>

            <div className="px-4 py-3 border-b border-gray-800">
                <div className="text-xs text-gray-500 mb-2">
                    被 <span className="text-gray-300">{inNeighbors.length}</span> 份文档引用
                </div>
                {inNeighbors.length === 0
                    ? <p className="text-xs text-gray-600">—</p>
                    : <div className="space-y-1">
                        {inNeighbors.map(id => (
                            <button key={id} onClick={() => onFocus(id)}
                                className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 transition-colors">
                                <span className="text-gray-600">←</span>
                                <span className="font-mono">{id}</span>
                            </button>
                        ))}
                    </div>
                }
            </div>

            <div className="px-4 py-3 flex flex-col gap-2">
                <Link href={`/library/${selected.id}`}
                    className="w-full text-center py-1.5 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors">
                    查看文档
                </Link>
                <Link href={`/query?q=${encodeURIComponent(selected.id)}`}
                    className="w-full text-center py-1.5 text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-lg transition-colors">
                    在此问答
                </Link>
                {!selected.is_center && (
                    <button onClick={() => onFocus(selected.id)}
                        className="w-full text-center py-1.5 text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-lg transition-colors">
                        聚焦此文档
                    </button>
                )}
            </div>
        </div>
    );
}
