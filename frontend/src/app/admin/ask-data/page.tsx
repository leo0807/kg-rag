"use client";
import { useState } from "react";
import { fetchApi } from "@/lib/api";
import { LineChart } from "@/components/charts/LineChart";
import { BarChart }  from "@/components/charts/BarChart";
import { PieChart }  from "@/components/charts/PieChart";
import { ScatterPlot } from "@/components/charts/ScatterPlot";

type QueryResult = {
  question: string;
  sql: string;
  data: Record<string, unknown>[];
  columns: string[];
  viz_type: string;
  viz_config: { x: string; y: string[] };
  error?: string;
};

const EXAMPLES = [
  "上个月哪些用户活跃度最高？",
  "每天的查询错误数量趋势",
  "不同评分等级的反馈数量分布",
  "最近创建的文档列表",
];

function ResultChart({ result }: { result: QueryResult }) {
  const { viz_type, viz_config, data } = result;
  const yKeys = viz_config.y.length ? viz_config.y : ["count"];
  const h = 260;

  if (viz_type === "line")
    return <LineChart data={data} xKey={viz_config.x} yKeys={yKeys} smooth height={h} />;
  if (viz_type === "bar")
    return <BarChart data={data} xKey={viz_config.x} yKeys={yKeys} height={h} />;
  if (viz_type === "pie") {
    const pieData = data.map(d => ({
      name: String(d[viz_config.x] ?? ""),
      value: Number(d[yKeys[0]] ?? 0),
    }));
    return <PieChart data={pieData} donut height={h} />;
  }
  if (viz_type === "scatter") {
    const sp = data.map(d => ({ x: Number(d[yKeys[0]] ?? 0), y: Number(d[yKeys[1]] ?? 0) }));
    return <ScatterPlot data={sp} height={h} />;
  }
  // Table fallback
  return (
    <div className="overflow-auto max-h-64 rounded border border-gray-800">
      <table className="w-full text-xs">
        <thead className="bg-gray-800 text-gray-400">
          <tr>{result.columns.map(c => <th key={c} className="text-left px-3 py-2">{c}</th>)}</tr>
        </thead>
        <tbody>
          {data.slice(0, 50).map((row, i) => (
            <tr key={i} className="border-t border-gray-800">
              {result.columns.map(c => (
                <td key={c} className="px-3 py-2 text-gray-300">{String(row[c] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AskDataPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult]     = useState<QueryResult | null>(null);
  const [loading, setLoading]   = useState(false);
  const [editSQL, setEditSQL]   = useState("");
  const [showSQL, setShowSQL]   = useState(false);

  const ask = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const d = await fetchApi<QueryResult>("/api/analytics/nl-query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      setResult(d);
      setEditSQL(d.sql ?? "");
    } finally {
      setLoading(false);
    }
  };

  const runSQL = async () => {
    if (!editSQL.trim()) return;
    setLoading(true);
    try {
      setResult(await fetchApi<QueryResult>("/api/analytics/nl-query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: "", raw_sql: editSQL }),
      }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-white">自然语言查询数据</h1>
        <p className="text-gray-400 text-sm mt-1">用中文描述你想了解的数据，AI 自动生成 SQL 并可视化</p>
      </div>

      {/* Input */}
      <div className="flex gap-3">
        <input
          className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
          placeholder="例：上个月每天的查询量趋势是什么？"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === "Enter" && ask(question)}
        />
        <button
          onClick={() => ask(question)}
          disabled={!question.trim() || loading}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-5 py-2.5 rounded-lg"
        >
          {loading ? "查询中…" : "查询"}
        </button>
      </div>

      {/* Examples */}
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map(e => (
          <button key={e} onClick={() => { setQuestion(e); ask(e); }}
            className="text-xs text-blue-400 bg-blue-950 hover:bg-blue-900 px-3 py-1.5 rounded-full border border-blue-800">
            {e}
          </button>
        ))}
      </div>

      {result && (
        <div className="space-y-4">
          {result.error && (
            <div className="bg-red-950 border border-red-800 text-red-300 text-sm px-4 py-3 rounded-lg">
              {result.error}
            </div>
          )}

          {/* SQL display */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg">
            <button
              onClick={() => setShowSQL(!showSQL)}
              className="w-full flex items-center justify-between px-4 py-3 text-sm"
            >
              <span className="text-gray-400">生成的 SQL</span>
              <span className="text-gray-600 text-xs">{showSQL ? "▲ 隐藏" : "▼ 查看/编辑"}</span>
            </button>
            {showSQL && (
              <div className="border-t border-gray-800 p-4 space-y-3">
                <textarea
                  className="w-full bg-gray-950 border border-gray-700 rounded p-3 text-xs text-green-300 font-mono h-28 focus:outline-none focus:border-blue-500"
                  value={editSQL}
                  onChange={e => setEditSQL(e.target.value)}
                />
                <button
                  onClick={runSQL}
                  disabled={loading}
                  className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-3 py-1.5 rounded"
                >
                  执行 SQL
                </button>
              </div>
            )}
          </div>

          {/* Chart */}
          {result.data.length > 0 && !result.error && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-xs">{result.data.length} 行数据 · {result.viz_type} 图</span>
              </div>
              <ResultChart result={result} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
