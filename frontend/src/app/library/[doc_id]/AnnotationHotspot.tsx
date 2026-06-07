"use client";

import { useState } from "react";

export interface HotspotAnnotation {
  id:        string;
  type:      string;  // tolerance | dimension | surface | fastener | other
  label:     string;  // raw 标注文字
  parameter: string;  // 参数名
  value:     string;
  unit:      string;
  // 相对坐标 0-1
  x: number;
  y: number;
  cps_ref?:  string;  // 关联的 CPS 规范
}

interface Props {
  annotation: HotspotAnnotation;
  containerWidth:  number;
  containerHeight: number;
  onClickCps?: (cpsRef: string) => void;
}

const TYPE_COLOR: Record<string, string> = {
  tolerance:  "bg-blue-500",
  dimension:  "bg-emerald-500",
  surface:    "bg-violet-500",
  fastener:   "bg-amber-500",
  other:      "bg-gray-500",
};

const TYPE_LABEL: Record<string, string> = {
  tolerance:  "公差",
  dimension:  "尺寸",
  surface:    "表面",
  fastener:   "紧固件",
  other:      "标注",
};

export function AnnotationHotspot({
  annotation,
  containerWidth,
  containerHeight,
  onClickCps,
}: Props) {
  const [showTooltip, setShowTooltip] = useState(false);

  const left = annotation.x * containerWidth;
  const top  = annotation.y * containerHeight;
  const color = TYPE_COLOR[annotation.type] ?? TYPE_COLOR.other;
  const typeLabel = TYPE_LABEL[annotation.type] ?? "标注";

  return (
    <div
      className="absolute"
      style={{ left, top, transform: "translate(-50%, -50%)" }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {/* 热点圆点 */}
      <div
        className={`w-4 h-4 rounded-full border-2 border-white ${color} cursor-pointer shadow-lg hover:scale-125 transition-transform`}
        title={annotation.label}
      />

      {/* 悬停工具提示 */}
      {showTooltip && (
        <div className="absolute z-50 bottom-6 left-1/2 -translate-x-1/2 w-52 bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-xl text-xs">
          <div className="flex items-center gap-1.5 mb-2">
            <span className={`w-2 h-2 rounded-full ${color}`} />
            <span className="font-medium text-gray-200">{typeLabel}</span>
          </div>
          {annotation.parameter && (
            <div className="text-gray-400 mb-1">
              <span className="text-gray-500">参数：</span>{annotation.parameter}
            </div>
          )}
          {annotation.value && (
            <div className="text-gray-300 mb-1">
              <span className="text-gray-500">值：</span>
              {annotation.value}{annotation.unit && ` ${annotation.unit}`}
            </div>
          )}
          {annotation.label && annotation.label !== annotation.parameter && (
            <div className="text-gray-500 text-[10px] mb-1.5 font-mono truncate">
              {annotation.label}
            </div>
          )}
          {annotation.cps_ref && (
            <button
              type="button"
              onClick={() => onClickCps?.(annotation.cps_ref!)}
              className="mt-1 text-[10px] text-[#1B6BB5] hover:underline"
            >
              → 查看 {annotation.cps_ref}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
