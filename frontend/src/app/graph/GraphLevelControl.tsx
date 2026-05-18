"use client";

import { ChevronDown, ChevronUp, Eye, EyeOff } from "lucide-react";
import type { GraphStats } from "./constants";

const LEVEL_LABELS: Record<number, string> = {
  0: "全部",
  1: "1级",
  2: "2级",
  3: "3级",
  4: "4级",
};

interface Props {
  showLevel: number;
  onShowLevel: (lv: number) => void;
  showImages: boolean;
  onToggleImages: () => void;
  showEntities: boolean;
  onToggleEntities: () => void;
  graphStats: GraphStats | null;
  onExpandAll: () => void;
  onCollapseToLevel1: () => void;
}

export function GraphLevelControl({
  showLevel,
  onShowLevel,
  showImages,
  onToggleImages,
  showEntities,
  onToggleEntities,
  graphStats,
  onExpandAll,
  onCollapseToLevel1,
}: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-t border-gray-800/60 bg-gray-900/80">
      <span className="text-xs text-gray-600 shrink-0">章节深度</span>
      <div className="flex flex-wrap items-center gap-0.5 shrink-0">
        {[0, 1, 2, 3, 4].map((lv) => (
          <button
            key={lv}
            type="button"
            onClick={() => onShowLevel(lv)}
            className={`shrink-0 whitespace-nowrap px-2 h-7 rounded text-xs font-medium transition-colors ${
              showLevel === lv
                ? "bg-amber-500 text-gray-950 font-semibold"
                : "text-gray-500 hover:text-gray-100 hover:bg-gray-800"
            }`}
          >
            {LEVEL_LABELS[lv]}
          </button>
        ))}
      </div>

      <div className="hidden w-px h-4 bg-gray-700 mx-1 shrink-0 sm:block" />

      <button
        type="button"
        onClick={onToggleImages}
        title={showImages ? "隐藏图片节点" : "显示图片节点"}
        className={`flex shrink-0 items-center gap-1 whitespace-nowrap px-2 h-7 rounded text-xs transition-colors ${
          showImages
            ? "text-pink-400 bg-pink-950/30"
            : "text-gray-600 hover:text-gray-300 hover:bg-gray-800"
        }`}
      >
        {showImages ? <Eye size={11} /> : <EyeOff size={11} />}
        图片
      </button>
      <button
        type="button"
        onClick={onToggleEntities}
        title={showEntities ? "隐藏实体节点" : "显示实体节点"}
        className={`flex shrink-0 items-center gap-1 whitespace-nowrap px-2 h-7 rounded text-xs transition-colors ${
          showEntities
            ? "text-emerald-400 bg-emerald-950/30"
            : "text-gray-600 hover:text-gray-300 hover:bg-gray-800"
        }`}
      >
        {showEntities ? <Eye size={11} /> : <EyeOff size={11} />}
        实体
      </button>

      <div className="hidden w-px h-4 bg-gray-700 mx-1 shrink-0 sm:block" />

      <button
        type="button"
        onClick={onExpandAll}
        className="flex shrink-0 items-center gap-1 whitespace-nowrap px-2 h-7 rounded text-xs text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors"
      >
        <ChevronDown size={11} />
        展开全部
      </button>
      <button
        type="button"
        onClick={onCollapseToLevel1}
        className="flex shrink-0 items-center gap-1 whitespace-nowrap px-2 h-7 rounded text-xs text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors"
      >
        <ChevronUp size={11} />
        收起到一级
      </button>

      <div className="flex-1" />

      {graphStats && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
          <span>文档 {graphStats.docs}</span>
          <span>·</span>
          <span>章节 {graphStats.sections}</span>
          {graphStats.images > 0 && (
            <>
              <span>·</span>
              <span>图片 {graphStats.images}</span>
            </>
          )}
          {graphStats.tables > 0 && (
            <>
              <span>·</span>
              <span>表格 {graphStats.tables}</span>
            </>
          )}
          {graphStats.entities > 0 && (
            <>
              <span>·</span>
              <span>实体 {graphStats.entities}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
