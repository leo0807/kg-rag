"use client";

import { useEffect } from "react";
import { useCypherBuilder, NODE_TYPES, REL_TYPES, REL_DIRS, NODE_PROPS, TEMPLATES } from "./useCypherBuilder";
import type { NodeType, RelType, RelDir } from "./useCypherBuilder";

function exportCSV(columns: string[], rows: Record<string, unknown>[]) {
  const esc = (v: unknown) => JSON.stringify(typeof v === "object" ? JSON.stringify(v) : String(v ?? ""));
  const blob = new Blob([columns.join(",") + "\n" + rows.map(r => columns.map(c => esc(r[c])).join(",")).join("\n")], { type: "text/csv" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "cypher_result.csv"; a.click();
}

function getIsAdmin() { try { return JSON.parse(localStorage.getItem("user") || "{}").is_admin === true; } catch { return false; } }

export default function AdminCypherPage() {
  const {
    nodeType, setNodeType, propKey, setPropKey, propVal, setPropVal,
    relType, setRelType, relDir, setRelDir, targetType, setTargetType,
    limitVal, setLimitVal, orderBy, setOrderBy,
    cypher, setCypher, running, result,
    buildCypher, execute, applyTemplate,
  } = useCypherBuilder();

  useEffect(() => { buildCypher(); }, [buildCypher]);

  if (typeof window !== "undefined" && !getIsAdmin()) {
    return <div className="p-8 text-red-400 text-sm">权限不足，仅管理员可访问</div>;
  }

  const sel = "w-full h-8 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 outline-none focus:border-indigo-500";

  return (
    <div className="h-full flex flex-col bg-gray-950 overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-6 py-3 border-b border-gray-800 flex items-center justify-between">
        <h1 className="text-base font-semibold text-white">Cypher 查询构造器</h1>
        <select onChange={e => { const t = TEMPLATES.find(x => x.label === e.target.value); if (t) applyTemplate(t); e.target.value = ""; }}
          defaultValue=""
          className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-300 outline-none">
          <option value="" disabled>选择查询模板…</option>
          {TEMPLATES.map(t => <option key={t.label} value={t.label}>{t.label}</option>)}
        </select>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: builder form */}
        <div className="w-68 shrink-0 border-r border-gray-800 p-4 overflow-auto space-y-4 text-xs">
          <Section label="起始节点">
            <select value={nodeType} onChange={e => setNodeType(e.target.value as NodeType)} className={sel + " mb-2"}>
              {NODE_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
            <div className="flex gap-1">
              <select value={propKey} onChange={e => setPropKey(e.target.value)} className="flex-1 h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 outline-none">
                <option value="">属性</option>
                {NODE_PROPS[nodeType].map(p => <option key={p}>{p}</option>)}
              </select>
              <input value={propVal} onChange={e => setPropVal(e.target.value)} placeholder="值"
                className="flex-1 h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 outline-none" />
            </div>
          </Section>

          <Section label="关系">
            <select value={relType} onChange={e => setRelType(e.target.value as RelType)} className={sel + " mb-2"}>
              {REL_TYPES.map(t => <option key={t} value={t}>{t || "（无关系）"}</option>)}
            </select>
            {relType && (
              <div className="flex gap-1 mb-2">
                {REL_DIRS.map(d => (
                  <button key={d} type="button" onClick={() => setRelDir(d as RelDir)}
                    className={`flex-1 h-7 rounded text-xs font-mono transition-colors ${relDir === d ? "bg-indigo-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>{d}</button>
                ))}
              </div>
            )}
            {relType && (
              <select value={targetType} onChange={e => setTargetType(e.target.value as NodeType)} className={sel}>
                <option value="">目标节点（任意）</option>
                {NODE_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
            )}
          </Section>

          <Section label="查询选项">
            <div className="space-y-2">
              <LabeledRow label="LIMIT">
                <input type="number" value={limitVal} onChange={e => setLimitVal(Math.min(100, Number(e.target.value)))} min={1} max={100}
                  className="flex-1 h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 outline-none" />
              </LabeledRow>
              <LabeledRow label="ORDER BY">
                <input value={orderBy} onChange={e => setOrderBy(e.target.value)} placeholder="e.g. s.seq_index DESC"
                  className="flex-1 h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 outline-none" />
              </LabeledRow>
            </div>
          </Section>

          <button onClick={buildCypher}
            className="w-full py-1.5 bg-gray-800 border border-gray-700 hover:border-indigo-500 text-gray-300 rounded-lg transition-colors">
            生成 Cypher ↑
          </button>
        </div>

        {/* Right: editor + results */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="shrink-0 p-4 border-b border-gray-800">
            <textarea value={cypher} onChange={e => setCypher(e.target.value)} rows={6} spellCheck={false}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs text-green-300 font-mono outline-none focus:border-indigo-500 resize-none" />
            <div className="flex items-center gap-2 mt-2">
              <button onClick={execute} disabled={running || !cypher.trim()}
                className="px-4 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 disabled:opacity-50">
                {running ? "执行中…" : "▶ 执行查询"}
              </button>
              {result && !result.error && <span className="text-xs text-gray-500">返回 {result.total} 行（上限 100）</span>}
              {result && !result.error && result.total > 0 && (
                <button onClick={() => exportCSV(result.columns, result.rows)}
                  className="ml-auto px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-400 text-xs rounded-lg hover:text-white">
                  导出 CSV
                </button>
              )}
            </div>
          </div>

          <div className="flex-1 overflow-auto p-4">
            {result?.error && (
              <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400 font-mono whitespace-pre-wrap">{result.error}</div>
            )}
            {result && !result.error && result.columns.length > 0 && (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-800 text-gray-400 text-left">
                    {result.columns.map(c => <th key={c} className="pb-2 pr-4 font-medium">{c}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row, i) => (
                    <tr key={i} className="border-b border-gray-800/40 hover:bg-gray-900/50">
                      {result.columns.map(c => (
                        <td key={c} className="py-1.5 pr-4 text-gray-300 max-w-xs">
                          <span className="truncate block" title={typeof row[c] === "object" ? JSON.stringify(row[c]) : String(row[c] ?? "")}>
                            {typeof row[c] === "object" ? JSON.stringify(row[c]) : String(row[c] ?? "—")}
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {!result && <div className="flex items-center justify-center h-32 text-gray-600 text-sm">配置查询后点击执行</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] text-gray-500 font-bold uppercase tracking-widest mb-2">{label}</div>
      {children}
    </div>
  );
}

function LabeledRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-400 w-16 shrink-0">{label}</span>
      {children}
    </div>
  );
}
