"use client";

import type { RetrievalRow } from "../types";

export function RetrievalResultsTable({ rows }: { rows: RetrievalRow[] }) {
  return (
    <div className="overflow-auto rounded-3xl border border-gray-800">
      <table className="min-w-[1300px] w-full text-sm">
        <thead className="bg-gray-950 text-gray-400">
          <tr>
            <th className="px-4 py-3 text-left">行号</th>
            <th className="px-4 py-3 text-left">结果</th>
            <th className="px-4 py-3 text-left">目标</th>
            <th className="px-4 py-3 text-left">问题</th>
            <th className="px-4 py-3 text-left">Gold Chunk</th>
            <th className="px-4 py-3 text-left">Gold Doc</th>
            <th className="px-4 py-3 text-left">命中位置</th>
            <th className="px-4 py-3 text-left">Recall</th>
            <th className="px-4 py-3 text-left">RR</th>
            <th className="px-4 py-3 text-left">NDCG</th>
            <th className="px-4 py-3 text-left">检索结果</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.row_no}-${row.question}`} className="align-top border-t border-gray-800">
              <td className="px-4 py-3 text-gray-500">{row.row_no}</td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${
                    row.matched ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"
                  }`}
                >
                  {row.matched ? "PASS" : "FAIL"}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-400">{row.target_type}</td>
              <td className="whitespace-pre-wrap px-4 py-3 text-gray-200">{row.question}</td>
              <td className="px-4 py-3 text-gray-400">{row.gold_chunk_ids.join(", ") || "—"}</td>
              <td className="px-4 py-3 text-gray-400">{row.gold_doc_ids.join(", ") || "—"}</td>
              <td className="px-4 py-3 text-gray-400">{row.hit_rank ?? "—"}</td>
              <td className="px-4 py-3 text-gray-400">{row.recall.toFixed(4)}</td>
              <td className="px-4 py-3 text-gray-400">{row.reciprocal_rank.toFixed(4)}</td>
              <td className="px-4 py-3 text-gray-400">{(row.ndcg ?? 0).toFixed(4)}</td>
              <td className="px-4 py-3 text-gray-500">
                {row.retrieved_chunk_ids.join(", ") || row.source_refs.join(", ") || "—"}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={11} className="px-4 py-10 text-center text-gray-500">
                暂无结果
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
