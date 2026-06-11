"use client";
import { useState, useRef } from "react";

type ImageItem = { url: string; label?: string };

interface Props {
  images: ImageItem[];
  title?: string;
  onClose?: () => void;
}

export function ResultViewer({ images, title = "结果查看器", onClose }: Props) {
  const [idx, setIdx]       = useState(0);
  const [scale, setScale]   = useState(1);
  const [playing, setPlay]  = useState(false);
  const timerRef            = useRef<ReturnType<typeof setInterval> | null>(null);

  const current = images[idx];

  const zoomIn  = () => setScale(s => Math.min(s + 0.25, 4));
  const zoomOut = () => setScale(s => Math.max(s - 0.25, 0.25));
  const reset   = () => setScale(1);

  const togglePlay = () => {
    if (playing) {
      if (timerRef.current) clearInterval(timerRef.current);
      setPlay(false);
    } else {
      setPlay(true);
      timerRef.current = setInterval(() => {
        setIdx(i => (i + 1) % images.length);
      }, 800);
    }
  };

  const screenshot = () => {
    if (!current?.url) return;
    const a = document.createElement("a");
    a.href = current.url;
    a.download = `screenshot_${idx + 1}.png`;
    a.click();
  };

  const exportCSV = () => {
    const rows = images.map((img, i) => `${i + 1},${img.label ?? ""},${img.url}`);
    const blob = new Blob([["index,label,url", ...rows].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "results.csv";
    a.click();
  };

  if (images.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-gray-900 border border-gray-800 rounded-lg text-gray-500">
        暂无云图
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
        <span className="text-white text-sm font-medium">{title}</span>
        <div className="flex items-center gap-2">
          {/* zoom */}
          <button onClick={zoomOut}  className="text-gray-400 hover:text-white text-lg px-1">－</button>
          <span className="text-gray-400 text-xs w-12 text-center">{Math.round(scale * 100)}%</span>
          <button onClick={zoomIn}   className="text-gray-400 hover:text-white text-lg px-1">＋</button>
          <button onClick={reset}    className="text-gray-500 hover:text-white text-xs px-2">重置</button>
          {/* animation */}
          {images.length > 1 && (
            <button onClick={togglePlay}
              className="text-gray-400 hover:text-white text-xs px-2 border border-gray-700 rounded">
              {playing ? "⏸ 停止" : "▶ 播放"}
            </button>
          )}
          {/* export */}
          <button onClick={screenshot} className="text-gray-400 hover:text-white text-xs px-2 border border-gray-700 rounded">
            截图
          </button>
          <button onClick={exportCSV}  className="text-gray-400 hover:text-white text-xs px-2 border border-gray-700 rounded">
            CSV
          </button>
          {onClose && (
            <button onClick={onClose} className="text-gray-500 hover:text-white ml-1">✕</button>
          )}
        </div>
      </div>

      {/* Viewport */}
      <div className="overflow-auto bg-black" style={{ maxHeight: "420px" }}>
        <div className="flex items-center justify-center min-h-48 p-4">
          {current?.url ? (
            <img
              src={current.url}
              alt={current.label ?? `帧 ${idx + 1}`}
              style={{ transform: `scale(${scale})`, transformOrigin: "center", transition: "transform 0.15s" }}
              className="max-w-full object-contain"
            />
          ) : (
            <div className="text-gray-500">图像不可用</div>
          )}
        </div>
      </div>

      {/* Film strip / navigation */}
      {images.length > 1 && (
        <div className="flex items-center gap-2 px-4 py-2 bg-gray-850 border-t border-gray-800 overflow-x-auto">
          {images.map((img, i) => (
            <button
              key={i}
              onClick={() => setIdx(i)}
              className={`shrink-0 w-12 h-9 rounded border text-xs overflow-hidden ${
                i === idx ? "border-blue-500" : "border-gray-700"
              }`}
            >
              {img.url ? (
                <img src={img.url} alt="" className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-gray-800 flex items-center justify-center text-gray-500">
                  {i + 1}
                </div>
              )}
            </button>
          ))}
        </div>
      )}

      {/* Frame label */}
      <div className="px-4 py-1.5 bg-gray-900 text-gray-500 text-xs flex justify-between">
        <span>{current?.label ?? `帧 ${idx + 1}`}</span>
        <span>{idx + 1} / {images.length}</span>
      </div>
    </div>
  );
}
