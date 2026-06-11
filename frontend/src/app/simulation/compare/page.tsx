"use client";
import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Legend } from "recharts";

type ResultRow = { result_name: string; max_value?: number; min_value?: number; unit: string; pass_status: string };
type CaseInfo = {
  id: string; case_name: string; domain: string; software: string;
  confidence_level: string; inputs: Record<string, unknown>;
  results: ResultRow[];
};

const AUTH = () => `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") : ""}`;
const COLORS = ["#3B82F6", "#F59E0B", "#10B981", "#8B5CF6"];

export default function ComparePage() {
  const [ids,      setIds]      = useState(["", ""]);
  const [cases,    setCases]    = useState<CaseInfo[]>([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");

  const addSlot  = () => ids.length < 4 && setIds([...ids, ""]);
  const updateId = (i: number, v: string) => setIds(ids.map((x, j) => j === i ? v : x));

  const compare = async () => {
    const validIds = ids.filter(Boolean);
    if (validIds.length < 2) { setError("至少输入 2 个案例 ID"); return; }
    setLoading(true); setError("");
    try {
      const headers = { "Content-Type": "application/json", Authorization: AUTH() };
      const r = await fetch("/api/simulation/compare", {
        method: "POST", headers,
        body: JSON.stringify({ case_ids: validIds }),
      });
      if (!r.ok) throw new Error(await r.text());
      setCases(await r.json());
    } catch (e: any) {
      setError(e.message ?? "对比失败");
    } finally {
      setLoading(false);
    }
  };

  // Build chart data aligned on result_name
  const resultNames = Array.from(new Set(cases.flatMap(c => c.results.map(r => r.result_name))));
  const chartData = resultNames.map(name => {
    const row: Record<string, unknown> = { name };
    cases.forEach((c, i) => {
      const r = c.results.find(x => x.result_name === name);
      row[`case${i}`] = r?.max_value ?? null;
    });
    return row;
  });

  // Build input param union
  const allKeys = Array.from(new Set(cases.flatMap(c => Object.keys(c.inputs || {}))));

  return (
    <div className="p-6 max-w-7xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-white">案例对比</h1>
        <p className="text-gray-400 text-sm mt-1">并排比较 2-4 个仿真案例的参数与结果</p>
      </div>

      {/* ID inputs */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
        <div className="grid grid-cols-4 gap-3">
          {ids.map((id, i) => (
            <div key={i}>
              <label className="text-gray-500 text-xs mb-1 block">案例 {i+1} ID</label>
              <input value={id} onChange={e => updateId(i, e.target.value)}
                placeholder="粘贴案例 UUID"
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm placeholder-gray-600" />
            </div>
          ))}
        </div>
        <div className="flex gap-3 items-center">
          {ids.length < 4 && (
            <button onClick={addSlot} className="text-xs text-gray-400 hover:text-white border border-gray-700 px-3 py-1.5 rounded">
              + 添加案例
            </button>
          )}
          <button onClick={compare} disabled={loading}
            className="px-5 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded">
            {loading ? "对比中…" : "开始对比"}
          </button>
          {error && <span className="text-red-400 text-xs">{error}</span>}
        </div>
      </div>

      {cases.length >= 2 && (
        <>
          {/* Case header row */}
          <div className={`grid gap-4`} style={{ gridTemplateColumns: `repeat(${cases.length}, 1fr)` }}>
            {cases.map((c, i) => (
              <div key={c.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4"
                style={{ borderTop: `3px solid ${COLORS[i]}` }}>
                <p className="text-white font-medium text-sm">{c.case_name}</p>
                <p className="text-gray-500 text-xs mt-1">{c.domain} · {c.software}</p>
                <span className={`text-xs px-2 py-0.5 rounded mt-2 inline-block ${
                  c.confidence_level === "已验证" ? "bg-green-900 text-green-300" :
                  c.confidence_level === "参考"   ? "bg-blue-900 text-blue-300" : "bg-yellow-900 text-yellow-300"
                }`}>{c.confidence_level}</span>
              </div>
            ))}
          </div>

          {/* Input params comparison table */}
          {allKeys.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
              <div className="px-4 py-2 bg-gray-800 text-white text-sm font-medium">输入参数对比</div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800">
                    <th className="px-4 py-2 text-left text-gray-400">参数</th>
                    {cases.map((_c, i) => (
                      <th key={i} className="px-4 py-2 text-left" style={{ color: COLORS[i] }}>案例 {i+1}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {allKeys.map(k => (
                    <tr key={k} className="border-t border-gray-800">
                      <td className="px-4 py-2 text-gray-400">{k}</td>
                      {cases.map((c, i) => (
                        <td key={i} className="px-4 py-2 text-white">{String(c.inputs?.[k] ?? "—")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Results bar chart */}
          {chartData.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <h3 className="text-white text-sm font-medium mb-3">关键结果对比</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 40, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" tick={{ fill: "#9CA3AF", fontSize: 11 }}
                    angle={-20} textAnchor="end" />
                  <YAxis tick={{ fill: "#9CA3AF", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#1F2937", border: "1px solid #374151" }} />
                  <Legend />
                  {cases.map((_, i) => (
                    <Bar key={i} dataKey={`case${i}`} fill={COLORS[i]} opacity={0.85} maxBarSize={40} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
