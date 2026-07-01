"use client";

import { fetchApi } from "@/lib/api";
import { Search, GitBranch, Link, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { ConstraintResults, type ConstraintResult } from "./ConstraintResults";
import { VersionLineage, type VersionData } from "./VersionLineage";
import { CrossRefResults, type CrossRefResult } from "./CrossRefResults";

type Tab = "constraints" | "version" | "cross-ref";

const INPUT = "w-full bg-gray-900/80 border border-gray-700/60 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-blue-500/70 focus:bg-gray-900 transition-colors placeholder-gray-600";
const LABEL = "block text-xs text-gray-500 mb-1.5 font-medium";
const BTN   = "px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg font-medium transition-colors disabled:opacity-40";

const TABS = [
  { id: "constraints" as Tab, label: "参数范围查询", Icon: SlidersHorizontal, desc: "按类型、单位和数值区间检索约束参数" },
  { id: "version"     as Tab, label: "版本溯源",     Icon: GitBranch,         desc: "追溯文档的历史版本与替代关系" },
  { id: "cross-ref"   as Tab, label: "跨规范引用",   Icon: Link,              desc: "查找引用特定规范的所有章节" },
];

export default function AdvancedSearchPage() {
  const [tab, setTab]     = useState<Tab>("constraints");
  const [cType, setCType] = useState("");
  const [minVal, setMinVal] = useState("");
  const [maxVal, setMaxVal] = useState("");
  const [unit, setUnit]   = useState("");
  const [cDocId, setCDocId] = useState("");
  const [cResults, setCResults] = useState<ConstraintResult[] | null>(null);
  const [vDocId, setVDocId] = useState("");
  const [vData, setVData] = useState<VersionData | null>(null);
  const [xTarget, setXTarget] = useState("");
  const [xResults, setXResults] = useState<CrossRefResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState("");

  async function searchConstraints() {
    setLoading(true); setError("");
    const p = new URLSearchParams({ type: cType, unit, doc_id: cDocId });
    if (minVal) p.set("min_val", minVal);
    if (maxVal) p.set("max_val", maxVal);
    try {
      const d = await fetchApi<{ results: ConstraintResult[] }>(`/api/search/constraints?${p}`);
      setCResults(d.results);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "查询失败"); }
    finally { setLoading(false); }
  }

  async function searchVersion() {
    if (!vDocId.trim()) return;
    setLoading(true); setError("");
    try {
      const d = await fetchApi<VersionData>(`/api/graph/version-lineage/${encodeURIComponent(vDocId)}`);
      setVData(d);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "查询失败"); }
    finally { setLoading(false); }
  }

  async function searchCrossRef() {
    if (!xTarget.trim()) return;
    setLoading(true); setError("");
    try {
      const d = await fetchApi<{ results: CrossRefResult[] }>(`/api/search/cross-references?target_doc=${encodeURIComponent(xTarget)}`);
      setXResults(d.results);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "查询失败"); }
    finally { setLoading(false); }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Hero */}
      <div className="rounded-2xl border border-gray-800 bg-[radial-gradient(ellipse_at_top_left,rgba(99,102,241,0.12),transparent_50%),#0f1117] p-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
            <Search size={15} className="text-indigo-400" />
          </div>
          <h1 className="text-lg font-semibold text-white">高级查询</h1>
        </div>
        <p className="text-sm text-gray-500 ml-11">结构化检索约束参数、版本溯源与跨规范引用关系</p>
      </div>

      {/* Tab selector */}
      <div className="grid grid-cols-3 gap-3">
        {TABS.map(t => (
          <button key={t.id} onClick={() => { setTab(t.id); setError(""); }}
            className={`text-left p-4 rounded-xl border transition-all ${
              tab === t.id
                ? "border-indigo-500/50 bg-indigo-950/40 shadow-[0_0_20px_rgba(99,102,241,0.08)]"
                : "border-gray-800 bg-gray-900/60 hover:border-gray-700 hover:bg-gray-900"
            }`}>
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center mb-2.5 ${
              tab === t.id ? "bg-indigo-500/15 border border-indigo-500/30" : "bg-gray-800 border border-gray-700"
            }`}><t.Icon size={14} className={tab === t.id ? "text-indigo-400" : "text-gray-500"} /></div>
            <div className={`text-sm font-medium mb-1 ${tab === t.id ? "text-white" : "text-gray-400"}`}>{t.label}</div>
            <div className="text-[11px] text-gray-600 leading-relaxed">{t.desc}</div>
          </button>
        ))}
      </div>

      {error && <div className="px-4 py-3 bg-red-950/40 border border-red-800/40 rounded-xl text-sm text-red-400">{error}</div>}

      {/* ── 参数范围查询 ── */}
      {tab === "constraints" && (
        <div className="space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div><label className={LABEL}>参数类型</label><input value={cType} onChange={e => setCType(e.target.value)} placeholder="如 temperature" className={INPUT} /></div>
              <div><label className={LABEL}>单位</label><input value={unit} onChange={e => setUnit(e.target.value)} placeholder="如 °C" className={INPUT} /></div>
              <div><label className={LABEL}>最小值</label><input type="number" value={minVal} onChange={e => setMinVal(e.target.value)} className={INPUT} /></div>
              <div><label className={LABEL}>最大值</label><input type="number" value={maxVal} onChange={e => setMaxVal(e.target.value)} className={INPUT} /></div>
            </div>
            <div className="flex gap-3">
              <input value={cDocId} onChange={e => setCDocId(e.target.value)} placeholder="文档 ID（留空则全局搜索）" className={`${INPUT} flex-1`} />
              <button onClick={searchConstraints} disabled={loading} className={BTN}>{loading ? "查询中…" : "查询"}</button>
            </div>
          </div>
          {cResults && <ConstraintResults results={cResults} />}
        </div>
      )}

      {/* ── 版本溯源 ── */}
      {tab === "version" && (
        <div className="space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex gap-3">
              <input value={vDocId} onChange={e => setVDocId(e.target.value)}
                placeholder="文档 ID（如 CPS-12345A）" className={`${INPUT} flex-1`}
                onKeyDown={e => e.key === "Enter" && searchVersion()} />
              <button onClick={searchVersion} disabled={loading} className={BTN}>{loading ? "查询中…" : "溯源"}</button>
            </div>
          </div>
          {vData && <VersionLineage data={vData} />}
        </div>
      )}

      {/* ── 跨规范引用 ── */}
      {tab === "cross-ref" && (
        <div className="space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex gap-3">
              <input value={xTarget} onChange={e => setXTarget(e.target.value)}
                placeholder="被引用的规范文档 ID" className={`${INPUT} flex-1`}
                onKeyDown={e => e.key === "Enter" && searchCrossRef()} />
              <button onClick={searchCrossRef} disabled={loading} className={BTN}>{loading ? "查询中…" : "查询"}</button>
            </div>
          </div>
          {xResults && <CrossRefResults results={xResults} />}
        </div>
      )}
    </div>
  );
}
