"use client";

import { X } from "lucide-react";
import { GraphNode, NODE_COLOR } from "./constants";

const API = "http://localhost:8000";

interface Props {
    node:    GraphNode;
    onClose: () => void;
}

export function NodeDetailSidebar({ node, onClose }: Props) {
    const type    = node.type || node.label;
    const color   = NODE_COLOR[type] ?? "#6b7280";
    const imgPath = node.path
        ? `${API}/${node.path.replace(/^.*?(uploads\/)/, "uploads/")}`
        : null;

    return (
        <div className="w-72 shrink-0 bg-gray-900 border-l border-gray-700 flex flex-col overflow-auto">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
                <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ backgroundColor: color + "33", color }}>
                    {type}
                </span>
                <button onClick={onClose} className="p-1 rounded hover:bg-gray-800 text-gray-500 hover:text-white transition-colors">
                    <X size={14} />
                </button>
            </div>

            <div className="px-4 py-3 border-b border-gray-800">
                <div className="text-sm font-semibold text-white leading-snug">{node.name || node.id}</div>
                {node.doc_id && <div className="text-xs text-gray-500 font-mono mt-1">{node.doc_id}</div>}
            </div>

            {imgPath && (
                <div className="px-4 py-3 border-b border-gray-800 bg-gray-950">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={imgPath} alt={node.name}
                        className="max-h-48 w-full object-contain rounded-lg"
                        onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
                </div>
            )}

            {node.description && (
                <div className="px-4 py-3 border-b border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">VLM 分析</div>
                    <p className="text-xs text-gray-300 leading-relaxed">{node.description}</p>
                </div>
            )}

            <div className="px-4 py-3 space-y-2">
                {Object.entries(node)
                    .filter(([k]) => !["id","name","label","type","x","y","fx","fy","description","path","content"].includes(k))
                    .map(([k, v]) => v != null && String(v) !== "" && (
                        <div key={k} className="flex gap-2">
                            <span className="text-xs text-gray-600 w-20 shrink-0">{k}</span>
                            <span className="text-xs text-gray-300 break-all">{String(v)}</span>
                        </div>
                    ))}
            </div>

            {type === "Document" && (
                <div className="px-4 pb-4 mt-auto">
                    <a href={`/library/${node.doc_id || node.id}`}
                        className="block w-full text-center px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded-lg transition-colors">
                        查看文档
                    </a>
                </div>
            )}
        </div>
    );
}
