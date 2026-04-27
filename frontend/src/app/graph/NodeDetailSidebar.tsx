"use client";

import { X } from "lucide-react";
import { GraphNode, NODE_COLOR } from "./constants";
import { ImageNodeDetail } from "./ImageNodeDetail";
import { AnnotationPanel } from "./AnnotationPanel";

interface Props {
    node:             GraphNode;
    onClose:          () => void;
    onExpandSection?: (chunkId: string) => void;
    expandingId?:     string | null;
}

export function NodeDetailSidebar({ node, onClose, onExpandSection, expandingId }: Props) {
    const type  = node.type || node.label;
    const color = NODE_COLOR[type] ?? "#6b7280";

    return (
        <div className="w-72 shrink-0 bg-gray-900 border-l border-gray-700 flex flex-col overflow-auto">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
                <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ backgroundColor: color + "33", color }}>
                    {type}
                </span>
                <button onClick={onClose} className="p-1 rounded hover:bg-gray-800 text-gray-500 hover:text-gray-100 transition-colors">
                    <X size={14} />
                </button>
            </div>

            {/* Name + doc_id */}
            <div className="px-4 py-3 border-b border-gray-800">
                <div className="text-sm font-semibold text-gray-100 leading-snug">{node.name || node.id}</div>
                {node.doc_id && <div className="text-xs text-gray-500 font-mono mt-1">{node.doc_id}</div>}
            </div>

            {/* Image-specific content */}
            {type === "Image" && <ImageNodeDetail node={node} />}

            {/* Generic description */}
            {type !== "Image" && node.description && (
                <div className="px-4 py-3 border-b border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">VLM 分析</div>
                    <p className="text-xs text-gray-300 leading-relaxed">{node.description}</p>
                </div>
            )}

            {/* Generic properties */}
            {type !== "Image" && (
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

            {/* Annotations */}
            <AnnotationPanel nodeId={node.id} nodeType={type} />

            {/* Expand section button */}
            {type === "Section" && node.has_children && onExpandSection && (
                <div className="px-4 pb-3">
                    <button onClick={() => onExpandSection(node.id)} disabled={expandingId === node.id}
                        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-amber-600/20 hover:bg-amber-600/40 border border-amber-600/40 text-amber-300 text-xs rounded-lg transition-colors disabled:opacity-50">
                        {expandingId === node.id ? "加载子节点…" : "展开子章节"}
                    </button>
                </div>
            )}

            {/* Document link */}
            {type === "Document" && (
                <div className="px-4 pb-4">
                    <a href={`/library/${node.doc_id || node.id}`}
                        className="block w-full text-center px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded-lg transition-colors">
                        查看文档
                    </a>
                </div>
            )}
        </div>
    );
}
