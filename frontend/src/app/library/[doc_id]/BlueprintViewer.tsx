"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { Maximize2, RefreshCw, ZoomIn, ZoomOut } from "lucide-react";
import { AnnotationHotspot } from "./AnnotationHotspot";
import type { HotspotAnnotation } from "./AnnotationHotspot";

interface BlueprintData {
  drawing_id:   string;
  title:        string;
  is_drawing:   boolean;
  parts:        { part_no: string; material?: string }[];
  fasteners:    { type: string; spec?: string }[];
  key_dimensions: { name: string; value: string; unit?: string }[];
  process_requirements: string[];
  annotations: {
    type: string; raw?: string; parameter?: string;
    value?: string; value_max?: string; value_min?: string; unit?: string;
  }[];
}

interface Props {
  imageId:  string;
  imageUrl: string;
  docId:    string;
  onClose?: () => void;
}

function _distributeAnnotations(annotations: BlueprintData["annotations"]): HotspotAnnotation[] {
  // 无 bbox 数据时，将标注均匀分布在图纸边缘（仅演示）
  return annotations.slice(0, 12).map((ann, i) => {
    const t = i / Math.max(annotations.length - 1, 1);
    return {
      id:        `ann_${i}`,
      type:      ann.type || "other",
      label:     ann.raw || ann.parameter || "",
      parameter: ann.parameter || "",
      value:     ann.value || "",
      unit:      ann.unit || "",
      x:         0.1 + (t * 0.8),
      y:         i % 2 === 0 ? 0.1 : 0.85,
    };
  });
}

export function BlueprintViewer({ imageId, imageUrl, docId, onClose }: Props) {
  const containerRef  = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 0, h: 0 });
  const [blueprint, setBlueprint] = useState<BlueprintData | null>(null);
  const [loading, setLoading]     = useState(false);
  const [zoom, setZoom]           = useState(1);
  const [hotspots, setHotspots]   = useState<HotspotAnnotation[]>([]);

  const loadAnnotations = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token") ?? "";
      const res = await fetch(`/api/blueprint/annotations/${imageId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data: BlueprintData = await res.json();
        setBlueprint(data);
        setHotspots(_distributeAnnotations(data.annotations));
      }
    } catch {
      // 加载失败静默处理
    } finally {
      setLoading(false);
    }
  }, [imageId]);

  useEffect(() => { loadAnnotations(); }, [loadAnnotations]);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(entries => {
      const entry = entries[0];
      if (entry) setDims({ w: entry.contentRect.width, h: entry.contentRect.height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  function handleCpsClick(cpsRef: string) {
    window.open(`/library?doc_id=${encodeURIComponent(cpsRef)}`, "_blank");
  }

  return (
    <div className="flex flex-col h-full bg-gray-950 rounded-xl overflow-hidden border border-gray-800">
      {/* 工具栏 */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-800 bg-gray-900">
        <span className="text-xs text-gray-400 font-medium truncate flex-1">
          {blueprint?.title || imageId}
        </span>
        <button type="button" onClick={() => setZoom(z => Math.min(z + 0.25, 3))}
          className="p-1 text-gray-500 hover:text-white">
          <ZoomIn size={14} />
        </button>
        <button type="button" onClick={() => setZoom(z => Math.max(z - 0.25, 0.5))}
          className="p-1 text-gray-500 hover:text-white">
          <ZoomOut size={14} />
        </button>
        <button type="button" onClick={() => setZoom(1)}
          className="text-[10px] text-gray-600 hover:text-gray-400 px-1">
          {Math.round(zoom * 100)}%
        </button>
        <button type="button" onClick={loadAnnotations} disabled={loading}
          className="p-1 text-gray-500 hover:text-white disabled:opacity-40">
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
        </button>
        {onClose && (
          <button type="button" onClick={onClose}
            className="p-1 text-gray-500 hover:text-white">
            <Maximize2 size={13} />
          </button>
        )}
      </div>

      {/* 图纸区域 */}
      <div className="flex-1 overflow-auto relative bg-gray-950">
        <div
          ref={containerRef}
          className="relative inline-block"
          style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }}
        >
          <Image
            src={imageUrl || `/api/images/${imageId}`}
            alt={blueprint?.title || imageId}
            width={800}
            height={600}
            unoptimized
            className="block max-w-none"
            onLoadingComplete={img => setDims({ w: img.offsetWidth, h: img.offsetHeight })}
          />
          {/* 标注热点叠加层 */}
          {dims.w > 0 && hotspots.map(hs => (
            <AnnotationHotspot
              key={hs.id}
              annotation={hs}
              containerWidth={dims.w}
              containerHeight={dims.h}
              onClickCps={handleCpsClick}
            />
          ))}
        </div>
      </div>

      {/* 下方信息面板 */}
      {blueprint && blueprint.is_drawing && (
        <div className="border-t border-gray-800 px-4 py-2 bg-gray-900 overflow-x-auto">
          <div className="flex gap-6 text-xs text-gray-500 whitespace-nowrap">
            {blueprint.parts.length > 0 && (
              <span>零件: {blueprint.parts.map(p => p.part_no).join(", ")}</span>
            )}
            {blueprint.fasteners.length > 0 && (
              <span>紧固件: {blueprint.fasteners.map(f => f.type).join(", ")}</span>
            )}
            {blueprint.key_dimensions.length > 0 && (
              <span>
                关键尺寸: {blueprint.key_dimensions.slice(0, 3).map(d => `${d.name}=${d.value}${d.unit || ""}`).join(", ")}
              </span>
            )}
            {blueprint.process_requirements.length > 0 && (
              <span className="text-blue-400">
                工艺: {blueprint.process_requirements[0]}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
