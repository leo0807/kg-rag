"use client";

import { type DragEvent, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  ArrowLeftRight, BarChart2, Brain, CopyX, Database, DatabaseZap,
  Expand, FileText, Filter, FlaskConical, GitBranch, GitFork,
  GitMerge, Highlighter, Layers, LayoutGrid, Link2, ListChecks,
  Maximize2, Merge, MessageSquare, PenLine, Quote, RefreshCw,
  Repeat, Search, SearchCode, Share2, Shuffle, SlidersHorizontal,
  Table, Table2, Type, Zap, Columns2,
} from "lucide-react";
import type { NodeTypeDef } from "./types";

interface Props {
  schema: Record<string, NodeTypeDef>;
  onAddNode: (nodeType: string) => void;
}

const ICON_MAP: Record<string, React.ElementType> = {
  // 检索
  vector_search:        Database,
  bm25_search:          Search,
  graph_search:         Share2,
  keyword_search:       Type,
  fuzzy_search:         SearchCode,
  semantic_search:      Brain,
  multi_query_search:   Layers,
  section_filter_search: Filter,
  table_search:         Table,
  // 处理
  rrf_fusion:           GitMerge,
  rerank:               BarChart2,
  hyde:                 Zap,
  graph_expand:         Maximize2,
  dedup:                CopyX,
  score_filter:         SlidersHorizontal,
  context_window:       Expand,
  keyword_highlight:    Highlighter,
  doc_diversity:        Shuffle,
  query_expand:         GitBranch,
  query_rewrite:        PenLine,
  mmr_diversity:        LayoutGrid,
  cross_encoder:        ArrowLeftRight,
  entity_link:          Link2,
  // 生成
  llm_generate:         MessageSquare,
  self_rag:             RefreshCw,
  summary_generate:     FileText,
  structured_extract:   Table2,
  checklist_generate:   ListChecks,
  compare_generate:     Columns2,
  citation_generate:    Quote,
  // 控制
  condition_branch:     GitFork,
  merge:                Merge,
  cache_check:          DatabaseZap,
  ab_test:              FlaskConical,
  feedback_loop:        Repeat,
};

const CATEGORY_ORDER = ["retrieval", "processing", "generation", "control"];
const CATEGORY_LABELS: Record<string, string> = {
  retrieval:  "检索",
  processing: "处理",
  generation: "输出",
  control:    "控制",
};
const CATEGORY_BG: Record<string, string> = {
  retrieval:  "bg-blue-500/20 hover:bg-blue-500/40 border-blue-500/30 text-blue-300",
  processing: "bg-orange-500/20 hover:bg-orange-500/40 border-orange-500/30 text-orange-300",
  generation: "bg-emerald-500/20 hover:bg-emerald-500/40 border-emerald-500/30 text-emerald-300",
  control:    "bg-violet-500/20 hover:bg-violet-500/40 border-violet-500/30 text-violet-300",
};

function setDragData(e: DragEvent, nodeType: string) {
  e.dataTransfer.setData("application/pipeline-node", nodeType);
  e.dataTransfer.effectAllowed = "copy";
}

interface NodeIconProps {
  nodeType: string;
  def: NodeTypeDef;
  onAdd: (nodeType: string) => void;
}

function NodeIcon({ nodeType, def, onAdd }: NodeIconProps) {
  const [tipPos, setTipPos] = useState<{ top: number; left: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const Icon = ICON_MAP[nodeType] ?? Database;
  const bg = CATEGORY_BG[def.category] ?? CATEGORY_BG.retrieval;

  function showTip() {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setTipPos({ top: rect.top, left: rect.right + 8 });
  }

  return (
    <div className="relative flex justify-center">
      <button
        ref={btnRef}
        type="button"
        draggable
        onDragStart={(e) => setDragData(e, nodeType)}
        onClick={() => onAdd(nodeType)}
        onMouseEnter={showTip}
        onMouseLeave={() => setTipPos(null)}
        className={`flex h-12 w-12 cursor-grab items-center justify-center rounded-xl border transition-colors active:opacity-70 ${bg}`}
        title={def.label}
      >
        <Icon size={20} />
      </button>

      {tipPos && typeof window !== "undefined" && createPortal(
        <div
          style={{ position: "fixed", top: tipPos.top, left: tipPos.left, zIndex: 9999 }}
          className="min-w-[160px] rounded-xl border border-gray-700 bg-gray-900 p-2.5 shadow-xl pointer-events-none"
        >
          <div className="mb-1 text-xs font-semibold text-white">{def.label}</div>
          <div className="text-[10px] text-gray-400">输入：{def.inputs.join(", ")}</div>
          <div className="text-[10px] text-gray-400">输出：{def.outputs.join(", ")}</div>
          {Object.keys(def.params).length > 0 && (
            <div className="mt-1 text-[10px] text-gray-500">
              参数：{Object.values(def.params).map((p) => p.label).join("、")}
            </div>
          )}
        </div>,
        document.body,
      )}
    </div>
  );
}

export function NodePanel({ schema, onAddNode }: Props) {
  const byCategory = CATEGORY_ORDER.reduce<Record<string, Array<[string, NodeTypeDef]>>>(
    (acc, cat) => {
      acc[cat] = Object.entries(schema).filter(([, def]) => def.category === cat);
      return acc;
    },
    {},
  );

  return (
    <div className="flex w-20 shrink-0 flex-col gap-4 overflow-y-auto border-r border-gray-800 bg-gray-950 py-3">
      {CATEGORY_ORDER.map((cat) => (
        <div key={cat} className="flex flex-col items-center gap-2">
          <div className="text-[9px] font-semibold uppercase tracking-widest text-gray-600">
            {CATEGORY_LABELS[cat]}
          </div>
          <div className="flex flex-col gap-2">
            {byCategory[cat]?.map(([nodeType, def]) => (
              <NodeIcon key={nodeType} nodeType={nodeType} def={def} onAdd={onAddNode} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
