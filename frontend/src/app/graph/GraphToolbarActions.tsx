"use client";

import {
  Check,
  Compass,
  Download,
  EyeOff,
  Layers,
  Settings,
  Share2,
} from "lucide-react";
import type { ReactNode } from "react";
import type { RenderMode } from "./constants";

interface Props {
  docFilter: string;
  setDocFilter: (v: string) => void;
  docs: { doc_id: string; title: string }[];
  hideIsolated: boolean;
  onToggleHideIsolated: () => void;
  isolatedCount: number;
  importanceMode: boolean;
  onToggleImportance: () => void;
  domainMode: boolean;
  onToggleDomain: () => void;
  showPredictions: boolean;
  onTogglePredictions: () => void;
  renderMode: RenderMode;
  manualMode: RenderMode | null;
  setManualMode: (v: RenderMode | null) => void;
  copied: boolean;
  shareSnapshot: () => void;
  showExport: boolean;
  setShowExport: (v: boolean) => void;
  exportGraph: (format: "json" | "graphml") => void;
  tourOpen: boolean;
  onTourToggle: () => void;
  showLimits: boolean;
  setShowLimits: (v: boolean) => void;
  showLegend: boolean;
  setShowLegend: (v: boolean) => void;
}

function ActionButton({
  active,
  title,
  onClick,
  children,
}: {
  active: boolean;
  title: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`flex shrink-0 items-center gap-1 whitespace-nowrap px-1.5 h-7 rounded text-[10px] font-medium transition-colors ${
        active
          ? "bg-indigo-600 text-white"
          : "text-gray-500 hover:text-gray-100 hover:bg-gray-800"
      }`}
    >
      {children}
    </button>
  );
}

export function GraphToolbarActions({
  docFilter,
  setDocFilter,
  docs,
  hideIsolated,
  onToggleHideIsolated,
  isolatedCount,
  importanceMode,
  onToggleImportance,
  domainMode,
  onToggleDomain,
  showPredictions,
  onTogglePredictions,
  renderMode,
  manualMode,
  setManualMode,
  copied,
  shareSnapshot,
  showExport,
  setShowExport,
  exportGraph,
  tourOpen,
  onTourToggle,
  showLimits,
  setShowLimits,
  showLegend,
  setShowLegend,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-1 px-1 py-0 sm:flex-nowrap sm:overflow-x-auto sm:whitespace-nowrap">
      <select
        value={docFilter}
        onChange={(e) => setDocFilter(e.target.value)}
        className="h-7 w-full max-w-full shrink-0 rounded border border-gray-700 bg-gray-800 px-1.5 text-[10px] text-gray-400 outline-none focus:border-indigo-500 sm:max-w-[80px]"
      >
        <option value="">全部文档</option>
        {docs.map((d) => (
          <option key={d.doc_id} value={d.doc_id}>
            {d.doc_id}
          </option>
        ))}
      </select>

      <ActionButton
        active={hideIsolated}
        title={
          hideIsolated
            ? `已隐藏 ${isolatedCount} 个孤立文档`
            : "显示所有文档（含孤立节点）"
        }
        onClick={onToggleHideIsolated}
      >
        <EyeOff size={12} />
        <span className="hidden sm:inline">隐藏孤立</span>
        {hideIsolated && isolatedCount > 0 && (
          <span className="font-mono text-indigo-400">{isolatedCount}</span>
        )}
      </ActionButton>

      <div className="hidden h-3.5 w-px shrink-0 bg-gray-700 sm:block" />
      <ActionButton
        active={importanceMode}
        title="按节点重要性着色"
        onClick={onToggleImportance}
      >
        🔥 热力
      </ActionButton>
      <ActionButton
        active={domainMode}
        title="按文档领域着色"
        onClick={onToggleDomain}
      >
        🏷 领域
      </ActionButton>
      <ActionButton
        active={showPredictions}
        title="显示/隐藏AI预测关系（虚线紫色）"
        onClick={onTogglePredictions}
      >
        ✦ 预测
      </ActionButton>
      <div className="hidden h-3.5 w-px shrink-0 bg-gray-700 sm:block" />

      <div className="flex shrink-0 items-center rounded bg-gray-800/60 px-0.5 py-0">
        {(["svg", "canvas", "webgl"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setManualMode(manualMode === m ? null : m)}
            title={
              m === "svg"
                ? "SVG（少量节点）"
                : m === "canvas"
                  ? "Canvas（中量）"
                  : "WebGL（海量）"
            }
            className={`shrink-0 px-0.5 h-4 rounded text-[10px] font-mono transition-colors ${
              renderMode === m
                ? "bg-indigo-600 text-white"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {m === "svg" ? "SVG" : m === "canvas" ? "2D" : "3D"}
          </button>
        ))}
      </div>

      <div className="h-3.5 w-px shrink-0 bg-gray-700" />
      <ActionButton active={tourOpen} title="图谱漫游" onClick={onTourToggle}>
        <Compass size={12} />
        {!tourOpen && <span className="hidden sm:inline">漫游</span>}
      </ActionButton>
      <ActionButton
        active={showLimits}
        title="节点数量"
        onClick={() => {
          setShowLimits(!showLimits);
          setShowLegend(false);
        }}
      >
        <Settings size={12} />
      </ActionButton>
      <ActionButton
        active={showLegend}
        title="图例"
        onClick={() => {
          setShowLegend(!showLegend);
          setShowLimits(false);
        }}
      >
        <Layers size={12} />
      </ActionButton>
      <ActionButton
        active={copied}
        title="复制分享链接"
        onClick={shareSnapshot}
      >
        {copied ? <Check size={12} /> : <Share2 size={12} />}
      </ActionButton>

      <div className="relative shrink-0">
        <ActionButton
          active={showExport}
          title="导出"
          onClick={() => setShowExport(!showExport)}
        >
          <Download size={12} />
        </ActionButton>
        {showExport && (
          <div className="absolute right-0 top-full z-30 mt-1 w-[88px] rounded-lg border border-gray-700 bg-gray-900 py-0.5 shadow-xl">
            <button
              type="button"
              onClick={() => {
                exportGraph("json");
                setShowExport(false);
              }}
              className="w-full px-2 py-0.5 text-left text-[10px] text-gray-300 hover:bg-gray-800"
            >
              导出 JSON
            </button>
            <button
              type="button"
              onClick={() => {
                exportGraph("graphml");
                setShowExport(false);
              }}
              className="w-full px-2 py-0.5 text-left text-[10px] text-gray-300 hover:bg-gray-800"
            >
              导出 GraphML
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
