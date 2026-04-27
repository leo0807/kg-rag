"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

export function SearchTab({
  showMsg,
  showError,
}: {
  showMsg: (m: string) => void;
  showError: (e: string) => void;
}) {
  const [alpha, setAlpha] = useState(0.5);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchApi<{ alpha: number }>("/api/admin/ops/hybrid-alpha")
      .then((d) => setAlpha(d.alpha))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setSaving(true);
    try {
      await fetchApi("/api/admin/ops/hybrid-alpha", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alpha }),
      });
      showMsg("配置已保存");
    } catch {
      showError("保存失败");
    } finally {
      setSaving(false);
    }
  }

  const bm25Pct = Math.round(alpha * 100);
  const vecPct = 100 - bm25Pct;

  return (
    <div className="space-y-6">
      {/* Alpha slider card */}
      <div className="bg-gray-950 border border-gray-800 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white mb-1">混合检索权重配置</h3>
        <p className="text-xs text-gray-500 mb-6">
          适用于 <span className="font-mono text-indigo-400">hybrid_es</span> 策略。
          调整 BM25 关键词检索与向量语义检索的融合比例。
        </p>

        {loading ? (
          <div className="h-24 flex items-center justify-center text-gray-500 text-sm">加载中…</div>
        ) : (
          <>
            {/* Visual bar */}
            <div className="flex rounded-lg overflow-hidden mb-4 h-8 text-xs font-medium">
              <div
                className="flex items-center justify-center bg-indigo-600 text-white transition-all duration-200"
                style={{ width: `${bm25Pct}%` }}
              >
                {bm25Pct > 15 && `BM25 ${bm25Pct}%`}
              </div>
              <div
                className="flex items-center justify-center bg-emerald-600 text-white transition-all duration-200"
                style={{ width: `${vecPct}%` }}
              >
                {vecPct > 15 && `向量 ${vecPct}%`}
              </div>
            </div>

            {/* Slider */}
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={alpha}
              onChange={(e) => setAlpha(parseFloat(e.target.value))}
              className="w-full accent-indigo-500 cursor-pointer"
            />

            {/* Labels */}
            <div className="flex justify-between text-xs text-gray-500 mt-1 mb-5">
              <span>α = 0.0 → 纯语义向量</span>
              <span>α = {alpha.toFixed(2)}</span>
              <span>α = 1.0 → 纯关键词 BM25</span>
            </div>

            {/* Presets */}
            <div className="flex gap-2 mb-6">
              {[
                { label: "纯关键词", v: 1.0 },
                { label: "偏关键词", v: 0.7 },
                { label: "均衡（推荐）", v: 0.5 },
                { label: "偏语义", v: 0.3 },
                { label: "纯语义", v: 0.0 },
              ].map(({ label, v }) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setAlpha(v)}
                  className={`px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                    Math.abs(alpha - v) < 0.01
                      ? "bg-indigo-600 text-white border-indigo-600"
                      : "text-gray-400 border-gray-700 hover:text-white hover:border-gray-500"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Description table */}
            <div className="rounded-lg border border-gray-800 overflow-hidden text-xs mb-6">
              <div className="grid grid-cols-3 bg-gray-900 text-gray-500 px-4 py-2 font-medium">
                <span>α 值</span><span>BM25 权重</span><span>适用场景</span>
              </div>
              {[
                { a: "1.0", b: "100%", s: "精确术语、型号编号、代码检索" },
                { a: "0.7", b: "70%",  s: "偏关键词，兼顾语义" },
                { a: "0.5", b: "50%",  s: "均衡混合（默认推荐）" },
                { a: "0.3", b: "30%",  s: "偏语义，容忍同义词变体" },
                { a: "0.0", b: "0%",   s: "纯语义，近义词/跨语言场景" },
              ].map((row) => (
                <div key={row.a} className="grid grid-cols-3 px-4 py-2 border-t border-gray-800 text-gray-400">
                  <span className="font-mono text-indigo-400">{row.a}</span>
                  <span>{row.b}</span>
                  <span>{row.s}</span>
                </div>
              ))}
            </div>

            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="px-5 py-2 rounded-lg bg-indigo-600 text-white text-sm
                         hover:bg-indigo-500 disabled:opacity-50 transition-colors"
            >
              {saving ? "保存中…" : "保存配置"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
