"use client";

import { Check, Pencil, X, X as XIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { AnnotationPanel } from "./AnnotationPanel";
import { type GraphNode, NODE_COLOR } from "./constants";
import { ImageNodeDetail } from "./ImageNodeDetail";

interface Props {
  node: GraphNode;
  onClose: () => void;
  onExpandSection?: (chunkId: string) => void;
  expandingId?: string | null;
}

const EDITABLE_SKIP = [
  "id",
  "name",
  "label",
  "type",
  "x",
  "y",
  "fx",
  "fy",
  "description",
  "path",
  "url",
  "content",
  "chunk_id",
];

export function NodeDetailSidebar({
  node,
  onClose,
  onExpandSection,
  expandingId,
}: Props) {
  const type = node.type || node.label;
  const color = NODE_COLOR[type] ?? "#6b7280";

  const [isAdmin, setIsAdmin] = useState(false);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    try {
      setIsAdmin(
        JSON.parse(localStorage.getItem("user") || "{}").is_admin === true,
      );
    } catch {
      /* ignore */
    }
  }, []);

  async function saveEdit() {
    if (!editingKey) return;
    setSaving(true);
    try {
      const token = localStorage.getItem("token") ?? "";
      await fetch(`/api/graph/nodes/${encodeURIComponent(node.id)}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ properties: { [editingKey]: editValue } }),
      });
      setEditingKey(null);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="w-full shrink-0 bg-gray-900 flex flex-col overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <span
          className="text-xs px-2 py-0.5 rounded-full font-medium"
          style={{ backgroundColor: `${color}33`, color }}
        >
          {type}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded hover:bg-gray-800 text-gray-500 hover:text-gray-100 transition-colors"
        >
          <X size={14} />
        </button>
      </div>

      {/* Name + doc_id */}
      <div className="px-4 py-3 border-b border-gray-800">
        <div className="text-sm font-semibold text-gray-100 leading-snug">
          {node.name || node.id}
        </div>
        {node.doc_id && (
          <div className="text-xs text-gray-500 font-mono mt-1">
            {node.doc_id}
          </div>
        )}
      </div>

      {/* Image-specific content */}
      {type === "Image" && <ImageNodeDetail node={node} />}

      {/* Generic description */}
      {type !== "Image" && node.description && (
        <div className="px-4 py-3 border-b border-gray-800">
          <div className="text-xs text-gray-500 mb-1">VLM 分析</div>
          <p className="text-xs text-gray-300 leading-relaxed">
            {node.description}
          </p>
        </div>
      )}

      {/* Generic properties */}
      {type !== "Image" && (
        <div className="px-4 py-3 space-y-2 border-b border-gray-800">
          {Object.entries(node)
            .filter(([k]) => !EDITABLE_SKIP.includes(k))
            .map(
              ([k, v]) =>
                v != null &&
                String(v) !== "" && (
                  <div key={k} className="flex gap-2 group items-start">
                    <span className="text-xs text-gray-600 w-20 shrink-0">
                      {k}
                    </span>
                    {editingKey === k ? (
                      <div className="flex items-center gap-1 flex-1 min-w-0">
                        <input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveEdit();
                            if (e.key === "Escape") setEditingKey(null);
                          }}
                          className="flex-1 min-w-0 text-xs bg-gray-800 border border-indigo-500 rounded px-1.5 py-0.5 text-gray-100 outline-none"
                        />
                        <button
                          type="button"
                          onClick={saveEdit}
                          disabled={saving}
                          className="text-green-400 hover:text-green-300 disabled:opacity-40"
                        >
                          <Check size={12} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingKey(null)}
                          className="text-gray-500 hover:text-gray-300"
                        >
                          <XIcon size={12} />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-start gap-1 flex-1 min-w-0">
                        <span className="text-xs text-gray-300 break-all flex-1">
                          {String(v)}
                        </span>
                        {isAdmin && (
                          <button
                            type="button"
                            onClick={() => {
                              setEditingKey(k);
                              setEditValue(String(v));
                            }}
                            className="opacity-0 group-hover:opacity-100 shrink-0 text-gray-600 hover:text-indigo-400 transition-opacity"
                          >
                            <Pencil size={11} />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ),
            )}
        </div>
      )}

      {/* Annotations */}
      <AnnotationPanel nodeId={node.id} nodeType={type} />

      {/* Expand section button */}
      {type === "Section" && node.has_children && onExpandSection && (
        <div className="px-4 pb-3">
          <button
            type="button"
            onClick={() => onExpandSection(node.id)}
            disabled={expandingId === node.id}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-amber-600/20 hover:bg-amber-600/40 border border-amber-600/40 text-amber-300 text-xs rounded-lg transition-colors disabled:opacity-50"
          >
            {expandingId === node.id ? "加载子节点…" : "展开子章节"}
          </button>
        </div>
      )}

      {/* Document link */}
      {type === "Document" && (
        <div className="px-4 pb-4">
          <a
            href={`/library/${node.doc_id || node.id}`}
            className="block w-full text-center px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded-lg transition-colors"
          >
            查看文档
          </a>
        </div>
      )}
    </div>
  );
}
