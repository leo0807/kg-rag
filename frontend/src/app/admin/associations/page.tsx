"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { GitBranch, Play, Check, X } from "lucide-react";

interface Association {
  doc_a: string;
  doc_b: string;
  common_entities: string[];
  confidence: number;
  support: number;
  lift: number;
  relationship: string;
  is_implicit: boolean;
}

interface MiningResult {
  associations: Association[];
  total: number;
  implicit: number;
  last_run: number | null;
}

function getToken() { return localStorage.getItem("token") ?? ""; }

export default function AssociationsPage() {
  const [data,      setData]      = useState<MiningResult | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [running,   setRunning]   = useState(false);
  const [filter,    setFilter]    = useState<"all" | "implicit">("implicit");
  const [confirmed, setConfirmed] = useState<Set<string>>(new Set());
  const [ignored,   setIgnored]   = useState<Set<string>>(new Set());
  const [msg,       setMsg]       = useState("");

  async function load() {
    setLoading(true);
    try {
      const res = await fetchApi<MiningResult>("/api/admin/associations");
      setData(res);
    } finally { setLoading(false); }
  }

  async function runMining() {
    setRunning(true);
    setMsg("挖掘任务已启动，请等待约 30 秒后刷新…");
    try {
      await fetchApi("/api/admin/associations/run", {
        method: "POST",
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      setTimeout(() => { load(); setRunning(false); }, 30000);
    } catch {
      setRunning(false);
    }
  }

  async function confirm(assoc: Association) {
    const key = `${assoc.doc_a}|${assoc.doc_b}`;
    await fetchApi("/api/admin/associations/confirm", {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        doc_a: assoc.doc_a,
        doc_b: assoc.doc_b,
        reason: `共同涉及：${assoc.common_entities.slice(0, 3).join("、")}`,
      }),
    });
    setConfirmed(prev => new Set([...prev, key]));
  }

  useEffect(() => { load(); }, []);

  const rows = (data?.associations ?? []).filter(a => {
    const key = `${a.doc_a}|${a.doc_b}`;
    if (ignored.has(key)) return false;
    return filter === "all" || a.is_implicit;
  });

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <GitBranch size={18} className="text-indigo-400" /> 隐性关联发现报告
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            {data ? `共发现 ${data.total} 组关联，其中隐性 ${data.implicit} 组` : "加载中…"}
            {data?.last_run && (
              <span className="ml-2">· 上次挖掘：{new Date(data.last_run * 1000).toLocaleString()}</span>
            )}
          </p>
        </div>
        <button
          onClick={runMining}
          disabled={running}
          className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors disabled:opacity-50"
        >
          <Play size={13} /> {running ? "挖掘中…" : "重新挖掘"}
        </button>
      </div>

      {msg && (
        <div className="px-3 py-2 bg-blue-500/10 border border-blue-500/30 rounded-lg text-xs text-blue-300">{msg}</div>
      )}

      {/* 过滤器 */}
      <div className="flex gap-2">
        {(["implicit", "all"] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-lg text-xs border transition-colors ${
              filter === f ? "bg-indigo-600 border-indigo-500 text-white" : "border-gray-700 text-gray-400 hover:text-white"
            }`}>
            {f === "implicit" ? "仅隐性关联" : "全部"}
          </button>
        ))}
      </div>

      {/* 关联表格 */}
      {loading ? (
        <div className="text-center text-sm text-gray-500 py-12">加载中…</div>
      ) : rows.length === 0 ? (
        <div className="text-center text-sm text-gray-500 py-12">
          暂无数据。点击"重新挖掘"开始关联规则挖掘。
        </div>
      ) : (
        <div className="rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-900 text-gray-400 text-left">
                <th className="px-4 py-3 font-medium">文档A</th>
                <th className="px-4 py-3 font-medium">文档B</th>
                <th className="px-4 py-3 font-medium">置信度</th>
                <th className="px-4 py-3 font-medium">提升度</th>
                <th className="px-4 py-3 font-medium">共同实体</th>
                <th className="px-4 py-3 font-medium">类型</th>
                <th className="px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {rows.map(assoc => {
                const key = `${assoc.doc_a}|${assoc.doc_b}`;
                const isConfirmed = confirmed.has(key);
                return (
                  <tr key={key} className="bg-gray-950 hover:bg-gray-900/60 transition-colors">
                    <td className="px-4 py-3 font-mono text-indigo-400">{assoc.doc_a}</td>
                    <td className="px-4 py-3 font-mono text-indigo-400">{assoc.doc_b}</td>
                    <td className="px-4 py-3 text-white">{(assoc.confidence * 100).toFixed(0)}%</td>
                    <td className="px-4 py-3 text-gray-300">{assoc.lift.toFixed(2)}</td>
                    <td className="px-4 py-3 text-gray-300 max-w-xs">
                      <div className="flex flex-wrap gap-1">
                        {assoc.common_entities.slice(0, 4).map(e => (
                          <span key={e} className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-400">{e}</span>
                        ))}
                        {assoc.common_entities.length > 4 && (
                          <span className="text-gray-600">+{assoc.common_entities.length - 4}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full border text-[10px] ${
                        assoc.is_implicit
                          ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
                          : "border-blue-700 bg-blue-950/40 text-blue-300"
                      }`}>
                        {assoc.relationship}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {isConfirmed ? (
                        <span className="text-emerald-400 text-[10px]">已建立关联</span>
                      ) : (
                        <div className="flex gap-1.5">
                          <button onClick={() => confirm(assoc)}
                            className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-900/40 border border-emerald-700/60 text-emerald-300 hover:bg-emerald-800/50 transition-colors">
                            <Check size={10} /> 确认
                          </button>
                          <button onClick={() => setIgnored(prev => new Set([...prev, key]))}
                            className="flex items-center gap-1 px-2 py-1 rounded bg-gray-800 border border-gray-700 text-gray-400 hover:text-white transition-colors">
                            <X size={10} /> 忽略
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
