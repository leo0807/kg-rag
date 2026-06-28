"use client";

import { fetchApi } from "@/lib/api";
import { Search, GitBranch, Link } from "lucide-react";
import { useState } from "react";

type Tab = "constraints" | "version" | "cross-ref";

interface ConstraintResult {
  chunk_id: string; doc_id: string; number: string; title: string;
  c_type: string; value: string; value_min: string; value_max: string;
  unit: string; description: string;
}

interface VersionDoc { id: string; title: string; version: string }
interface VersionData {
  doc_id: string; title: string; version: string;
  newer_versions: VersionDoc[]; older_versions: VersionDoc[];
}

interface CrossRefResult { doc_id: string; doc_title: string; chunk_id: string; number: string; title: string }

export default function AdvancedSearchPage() {
  const [tab, setTab] = useState<Tab>("constraints");

  // 参数范围查询状态
  const [cType,   setCType]   = useState("");
  const [minVal,  setMinVal]  = useState("");
  const [maxVal,  setMaxVal]  = useState("");
  const [unit,    setUnit]    = useState("");
  const [cDocId,  setCDocId]  = useState("");
  const [cResults, setCResults] = useState<ConstraintResult[] | null>(null);

  // 版本溯源状态
  const [vDocId,   setVDocId]  = useState("");
  const [vData,    setVData]   = useState<VersionData | null>(null);

  // 跨引用查询
  const [xTarget,  setXTarget] = useState("");
  const [xResults, setXResults] = useState<CrossRefResult[] | null>(null);

  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  async function searchConstraints() {
    setLoading(true); setError("");
    const p = new URLSearchParams({ type: cType, unit, doc_id: cDocId });
    if (minVal) p.set("min_val", minVal);
    if (maxVal) p.set("max_val", maxVal);
    try {
      const d = await fetchApi<{ results: ConstraintResult[] }>(`/api/search/constraints?${p}`);
      setCResults(d.results);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "查询失败");
    } finally { setLoading(false); }
  }

  async function searchVersion() {
    if (!vDocId.trim()) return;
    setLoading(true); setError("");
    try {
      const d = await fetchApi<VersionData>(`/api/graph/version-lineage/${encodeURIComponent(vDocId)}`);
      setVData(d);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "查询失败");
    } finally { setLoading(false); }
  }

  async function searchCrossRef() {
    if (!xTarget.trim()) return;
    setLoading(true); setError("");
    try {
      const d = await fetchApi<{ results: CrossRefResult[] }>(`/api/search/cross-references?target_doc=${encodeURIComponent(xTarget)}`);
      setXResults(d.results);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "查询失败");
    } finally { setLoading(false); }
  }

  const TABS: { id: Tab; label: string; icon: typeof Search }[] = [
    { id: "constraints", label: "参数范围查询", icon: Search },
    { id: "version",     label: "版本溯源",     icon: GitBranch },
    { id: "cross-ref",   label: "跨规范引用",   icon: Link },
  ];

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-lg font-semibold text-gray-100 mb-6" style={{ animation: "slide-up-fade 0.55s ease both" }}>高级查询</h1>

      <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-lg p-0.5 w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => { setTab(t.id); setError(""); }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-colors ${
              tab === t.id ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-gray-300"
            }`}>
            <t.icon size={12} />{t.label}
          </button>
        ))}
      </div>

      {error && <div className="mb-4 text-xs text-red-400 bg-red-900/20 px-3 py-2 rounded">{error}</div>}

      {tab === "constraints" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">参数类型</label>
              <input value={cType} onChange={e => setCType(e.target.value)}
                placeholder="如 temperature"
                className="w-full bg-gray-900 border border-gray-700 text-gray-200 text-sm rounded px-2.5 py-1.5" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">单位</label>
              <input value={unit} onChange={e => setUnit(e.target.value)}
                placeholder="如 °C"
                className="w-full bg-gray-900 border border-gray-700 text-gray-200 text-sm rounded px-2.5 py-1.5" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">最小值</label>
              <input value={minVal} onChange={e => setMinVal(e.target.value)} type="number"
                className="w-full bg-gray-900 border border-gray-700 text-gray-200 text-sm rounded px-2.5 py-1.5" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">最大值</label>
              <input value={maxVal} onChange={e => setMaxVal(e.target.value)} type="number"
                className="w-full bg-gray-900 border border-gray-700 text-gray-200 text-sm rounded px-2.5 py-1.5" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <input value={cDocId} onChange={e => setCDocId(e.target.value)}
              placeholder="文档 ID（可选，留空全局搜索）"
              className="flex-1 bg-gray-900 border border-gray-700 text-gray-200 text-sm rounded px-2.5 py-1.5" />
            <button onClick={searchConstraints} disabled={loading}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded disabled:opacity-40">
              {loading ? "查询中…" : "查询"}
            </button>
          </div>
          {cResults && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-500">
                找到 {cResults.length} 条约束
              </div>
              <div className="divide-y divide-gray-800 max-h-[400px] overflow-y-auto animate-rows">
                {cResults.map(r => (
                  <div key={r.chunk_id} className="px-4 py-3 hover:bg-gray-800/30">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-indigo-400 font-mono">{r.doc_id} § {r.number}</span>
                      <span className="text-xs px-1.5 py-0.5 bg-emerald-900/40 text-emerald-400 rounded">
                        {r.c_type} · {r.value_min || r.value}{r.value_max ? `~${r.value_max}` : ""} {r.unit}
                      </span>
                    </div>
                    <div className="text-sm text-gray-300">{r.title}</div>
                    {r.description && <div className="text-xs text-gray-500 mt-0.5">{r.description}</div>}
                  </div>
                ))}
                {!cResults.length && <div className="px-4 py-6 text-center text-gray-600 text-sm">暂无匹配结果</div>}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "version" && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <input value={vDocId} onChange={e => setVDocId(e.target.value)}
              placeholder="输入文档 ID（如 CPS-12345A）"
              className="flex-1 bg-gray-900 border border-gray-700 text-gray-200 text-sm rounded px-2.5 py-1.5"
              onKeyDown={e => e.key === "Enter" && searchVersion()} />
            <button onClick={searchVersion} disabled={loading}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded disabled:opacity-40">
              {loading ? "查询中…" : "查询"}
            </button>
          </div>
          {vData && (
            <div className="space-y-3">
              <div className="bg-indigo-900/30 border border-indigo-800 rounded-lg px-4 py-3 text-sm">
                <span className="text-gray-400">当前版本：</span>
                <span className="text-indigo-300 font-medium">{vData.title || vData.doc_id}</span>
                {vData.version && <span className="ml-2 text-gray-500">(v{vData.version})</span>}
              </div>
              {vData.newer_versions.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-2">↑ 更新版本（此版本已被替代）</div>
                  {vData.newer_versions.map(d => (
                    <div key={d.id} className="bg-gray-900 border border-gray-800 rounded px-3 py-2 text-sm text-gray-300 mb-1">
                      {d.title || d.id}{d.version && <span className="ml-2 text-xs text-gray-500">v{d.version}</span>}
                    </div>
                  ))}
                </div>
              )}
              {vData.older_versions.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-2">↓ 历史版本（已被当前版本替代）</div>
                  {vData.older_versions.map(d => (
                    <div key={d.id} className="bg-gray-900 border border-gray-800/50 rounded px-3 py-2 text-sm text-gray-500 mb-1">
                      {d.title || d.id}{d.version && <span className="ml-2 text-xs">v{d.version}</span>}
                    </div>
                  ))}
                </div>
              )}
              {!vData.newer_versions.length && !vData.older_versions.length && (
                <div className="text-sm text-gray-600">该文档暂无已知版本链路</div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "cross-ref" && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <input value={xTarget} onChange={e => setXTarget(e.target.value)}
              placeholder="被引用的规范文档 ID"
              className="flex-1 bg-gray-900 border border-gray-700 text-gray-200 text-sm rounded px-2.5 py-1.5"
              onKeyDown={e => e.key === "Enter" && searchCrossRef()} />
            <button onClick={searchCrossRef} disabled={loading}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded disabled:opacity-40">
              {loading ? "查询中…" : "查询"}
            </button>
          </div>
          {xResults && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-500">
                {xResults.length} 个章节引用了此规范
              </div>
              <div className="divide-y divide-gray-800 max-h-[400px] overflow-y-auto animate-rows">
                {xResults.map(r => (
                  <div key={r.chunk_id} className="px-4 py-3 hover:bg-gray-800/30">
                    <div className="text-xs text-indigo-400 font-mono mb-1">{r.doc_title} § {r.number}</div>
                    <div className="text-sm text-gray-300">{r.title}</div>
                  </div>
                ))}
                {!xResults.length && <div className="px-4 py-6 text-center text-gray-600 text-sm">暂无引用记录</div>}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
