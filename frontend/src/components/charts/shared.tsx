"use client";
import React from "react";

export const COLORS = [
  "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6",
  "#06B6D4", "#F97316", "#EC4899", "#84CC16", "#6B7280",
];

export function ChartLoading({ height = 280 }: { height?: number }) {
  return (
    <div
      className="flex items-center justify-center bg-gray-900 rounded-lg animate-pulse"
      style={{ height }}
    >
      <span className="text-gray-600 text-sm">加载中…</span>
    </div>
  );
}

export function ChartEmpty({ height = 280, msg = "暂无数据" }: { height?: number; msg?: string }) {
  return (
    <div
      className="flex items-center justify-center bg-gray-900 rounded-lg border border-dashed border-gray-700"
      style={{ height }}
    >
      <span className="text-gray-500 text-sm">{msg}</span>
    </div>
  );
}

export function ChartWrapper({
  title,
  id,
  onExport,
  children,
}: {
  title?: string;
  id?: string;
  onExport?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div id={id} className="bg-gray-900 rounded-lg border border-gray-800 p-4">
      {(title || onExport) && (
        <div className="flex items-center justify-between mb-3">
          {title && <h3 className="text-white text-sm font-medium">{title}</h3>}
          {onExport && (
            <button onClick={onExport} className="text-xs text-gray-500 hover:text-gray-300">
              导出
            </button>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

export function exportChart(id?: string) {
  if (!id) return;
  const el = document.getElementById(id);
  if (!el) return;
  // Simple: open print dialog focused on chart
  const win = window.open("", "_blank");
  if (!win) return;
  win.document.write(`<html><body>${el.innerHTML}</body></html>`);
  win.print();
  win.close();
}

export function fmtNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
