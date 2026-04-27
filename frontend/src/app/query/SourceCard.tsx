"use client";

import { ExternalLink, Reply, Star } from "lucide-react";
import Link from "next/link";
import type { SourceSection } from "./types";

const RANK_COLORS = ["#fbbf24", "#34d399", "#60a5fa", "#f472b6", "#a78bfa"];
const SOURCE_LABELS: Record<string, string> = {
  fulltext: "全文", vector: "向量", graph: "图谱扩展", gnn: "GNN",
};

interface Props {
  source: SourceSection;
  index: number;
  onSourceClick?: (chunkId: string) => void;
  onQuoteSource?: (source: SourceSection) => void;
  onFavoriteSection?: (s: SourceSection) => void;
  favoritedChunkIds?: Set<string>;
  onToggleTrace: (trace: string) => void;
}

export function SourceCard({
  source: s, index: idx, onSourceClick, onQuoteSource,
  onFavoriteSection, favoritedChunkIds, onToggleTrace,
}: Props) {
  return (
    <div className="h-full rounded-xl border border-gray-800 bg-gray-950/55 px-2.5 py-2">
      <div className="flex items-start gap-2">
        <button
          type="button"
          onClick={() => { onSourceClick?.(s.chunk_id); onQuoteSource?.(s); }}
          title="点击追问此章节"
          className="group flex min-w-0 flex-1 items-start gap-2 rounded-lg border border-gray-700 bg-gray-800/70 px-2 py-1.5 text-left transition-colors hover:border-[#1B6BB5] hover:bg-[#1B6BB5]/10"
        >
          <span
            className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-gray-900"
            style={{ backgroundColor: RANK_COLORS[idx] ?? "#6b7280" }}
          >
            {idx + 1}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-mono text-[#1B6BB5] dark:text-[#5BA3E0]">{s.doc_id} §{s.number}</span>
              {s.page_idx !== undefined && (
                <span className="rounded bg-gray-900 px-1 py-0.5 text-[10px] text-gray-500">P{s.page_idx + 1}</span>
              )}
            </div>
            <div className="mt-0.5 truncate text-xs text-gray-300">{s.title}</div>
          </div>
          <Reply size={10} className="mt-0.5 flex-shrink-0 text-gray-600 transition-colors group-hover:text-[#1B6BB5]" />
        </button>

        <div className="flex flex-shrink-0 items-center gap-1">
          <Link
            href={`/library/${s.doc_id}${s.page_idx !== undefined ? `?page=${s.page_idx}` : ""}`}
            title="查看原文并跳转锚点"
            className="rounded-lg border border-gray-700 p-1.5 text-gray-500 transition-colors hover:border-[#1B6BB5] hover:text-[#1B6BB5]"
          >
            <ExternalLink size={10} />
          </Link>
          {onFavoriteSection && (
            <button
              type="button"
              onClick={() => onFavoriteSection(s)}
              title={favoritedChunkIds?.has(s.chunk_id) ? "取消收藏" : "收藏此章节"}
              className="rounded-lg border border-gray-700 p-1.5 transition-colors hover:border-amber-500"
            >
              <Star
                size={10}
                className={favoritedChunkIds?.has(s.chunk_id) ? "text-amber-400 fill-amber-400" : "text-gray-600 hover:text-amber-400"}
              />
            </button>
          )}
        </div>
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        {(s.source_type ?? []).map((type) => (
          <span
            key={`${s.chunk_id}_${type}`}
            className={`rounded-md border px-1.5 py-0.5 text-[10px] leading-4 ${
              type === "graph" ? "border-emerald-700 bg-emerald-950/50 text-emerald-300" :
              type === "vector" ? "border-sky-700 bg-sky-950/50 text-sky-300" :
              type === "fulltext" ? "border-amber-700 bg-amber-950/50 text-amber-300" :
              "border-violet-700 bg-violet-950/50 text-violet-300"
            }`}
          >
            {SOURCE_LABELS[type] ?? type}
          </span>
        ))}
        {s.is_graph_expanded && (
          <span className="rounded-md border border-emerald-800/80 bg-emerald-950/30 px-1.5 py-0.5 text-[10px] leading-4 text-emerald-200/80">
            扩展命中
          </span>
        )}
        {s.retrieval_trace && s.retrieval_trace.length > 0 && (
          <button
            type="button"
            onClick={() => onToggleTrace(s.retrieval_trace?.[0] ?? "")}
            className="max-w-full rounded-md border border-gray-800 bg-gray-900/80 px-1.5 py-0.5 font-mono text-[10px] leading-4 text-gray-500 transition-colors hover:border-gray-700 hover:text-gray-300"
            title={s.retrieval_trace.join(" -> ")}
          >
            <span className="mr-1 text-gray-600">trace</span>
            <span className="truncate">
              {s.retrieval_trace[0]}{s.retrieval_trace.length > 1 && ` +${s.retrieval_trace.length - 1}`}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
