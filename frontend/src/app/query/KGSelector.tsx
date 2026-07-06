"use client";

import { useEffect, useState } from "react";
import { GitBranch } from "lucide-react";
import { fetchApi } from "@/lib/api";

interface KGMeta {
  graph_id: string;
  doc_id: string;
  chapter: string;
  status: string;
  node_count?: number;
}

function graphLabel(g: KGMeta) {
  if (g.chapter === "ALL" && g.doc_id === "ALL") return "全局图谱";
  if (g.chapter === "ALL") return `全文 · ${g.doc_id.slice(0, 18)}`;
  return `Ch.${g.chapter} · ${g.doc_id.slice(0, 16)}`;
}

interface Props {
  /** Current doc_hints driven by this selector */
  value: string[];
  onChange: (hints: string[]) => void;
}

export function KGSelector({ value, onChange }: Props) {
  const [graphs, setGraphs] = useState<KGMeta[]>([]);

  useEffect(() => {
    fetchApi<KGMeta[]>("/api/graph/spo/list")
      .then(list => setGraphs(list.filter(g => g.status === "ready")))
      .catch(() => {});
  }, []);

  if (graphs.length === 0) return null;

  const selected = value.length > 0 ? value[0] : "";

  function handleChange(docId: string) {
    onChange(docId ? [docId] : []);
  }

  return (
    <div className="flex items-center gap-1.5">
      <GitBranch size={10} className="text-indigo-400 shrink-0" />
      <select
        value={selected}
        onChange={e => handleChange(e.target.value)}
        className="bg-gray-900 border border-gray-800 text-gray-400 text-[11px] rounded px-1.5 py-0.5 cursor-pointer hover:border-gray-600 transition-colors focus:outline-none focus:border-indigo-600"
      >
        <option value="">全部图谱</option>
        {graphs.map(g => (
          <option key={g.graph_id} value={g.doc_id !== "ALL" ? g.doc_id : ""}>
            {graphLabel(g)}
            {g.node_count != null ? ` (${g.node_count}节点)` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
