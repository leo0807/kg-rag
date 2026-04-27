"use client";

import { NODE_COLOR } from "./constants";

interface Props {
  heatMap: Map<string, number>;
  tourOpen: boolean;
}

export function GraphLegend({ heatMap, tourOpen }: Props) {
  return (
    <div className="absolute top-3 right-3 bg-gray-900 border border-gray-700 rounded-xl px-3 py-2.5 z-10 shadow-xl">
      <div className="text-xs text-gray-500 mb-2">节点类型</div>
      <div className="flex flex-col gap-1.5">
        {Object.entries(NODE_COLOR).map(([k, c]) => (
          <div key={k} className="flex items-center gap-2">
            <div className="w-7 shrink-0 flex justify-center">
              {k === "Document" && (
                <div className="w-5 h-3 rounded-md" style={{ backgroundColor: c }} />
              )}
              {k === "Section" && (
                <div className="w-6 h-3 rounded-full" style={{ backgroundColor: c }} />
              )}
              {k === "Image" && (
                <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: c }} />
              )}
              {k === "Constraint" && (
                <div className="w-4 h-4 rotate-45 rounded-[2px]" style={{ backgroundColor: c }} />
              )}
              {k === "Process" && (
                <div
                  className="w-5 h-4"
                  style={{ backgroundColor: c, clipPath: "polygon(14% 0%, 86% 0%, 100% 50%, 86% 100%, 14% 100%, 0% 50%)" }}
                />
              )}
              {!["Document", "Section", "Image", "Constraint", "Process"].includes(k) && (
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: c }} />
              )}
            </div>
            <span className="text-xs text-gray-400">{k}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 pt-2.5 border-t border-gray-800">
        <div className="text-xs text-gray-500 mb-2">章节外圈状态</div>
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <div className="relative w-9 h-5 shrink-0">
              <div className="absolute inset-0 rounded-full bg-amber-500/20 border border-orange-500/80" />
              <div className="absolute inset-[3px] rounded-full bg-amber-500" />
            </div>
            <span className="text-xs text-gray-400">搜索命中高亮</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative w-10 h-6 shrink-0">
              <div className="absolute inset-0 rounded-full border border-amber-500/70 bg-amber-500/10" />
              <div className="absolute inset-[4px] rounded-full bg-amber-500" />
            </div>
            <span className="text-xs text-gray-400">热点章节</span>
          </div>
          {tourOpen && (
            <div className="flex items-center gap-2">
              <div className="relative w-10 h-6 shrink-0">
                <div className="absolute inset-0 rounded-full border-2 border-amber-300 bg-amber-300/10" />
                <div className="absolute inset-[4px] rounded-full bg-amber-500" />
              </div>
              <span className="text-xs text-gray-400">漫游当前节点</span>
            </div>
          )}
          <div className="text-[11px] text-gray-600 leading-relaxed">无外圈表示普通章节节点。</div>
        </div>
      </div>
      {heatMap.size > 0 && (
        <div className="mt-3 pt-2.5 border-t border-gray-800">
          <div className="text-xs text-gray-500 mb-2">查询热力</div>
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5">
              {[0.2, 0.5, 1].map((v) => (
                <div
                  key={v}
                  className="rounded-full border border-amber-500/60"
                  style={{
                    width: Math.round(8 + v * 12),
                    height: Math.round(8 + v * 12),
                    backgroundColor: `rgba(245,158,11,${0.15 + v * 0.25})`,
                  }}
                />
              ))}
            </div>
            <span className="text-xs text-gray-400">低 → 高</span>
          </div>
          <div className="text-xs text-gray-600 mt-1">{heatMap.size} 个热点章节</div>
        </div>
      )}
    </div>
  );
}
