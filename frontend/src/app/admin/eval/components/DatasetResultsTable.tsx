"use client";

import type { EvalRow } from "../types";

export function DatasetResultsTable({ rows }: { rows: EvalRow[] }) {
  return (
    <section className="overflow-hidden rounded-3xl border border-gray-800 bg-gray-900">
      <div className="overflow-auto">
        <table className="min-w-[1100px] w-full text-sm">
          <thead className="bg-gray-950 text-gray-400">
            <tr>
              <th className="px-4 py-3 text-left">行号</th>
              <th className="px-4 py-3 text-left">结果</th>
              <th className="px-4 py-3 text-left">问题</th>
              <th className="px-4 py-3 text-left">标准答案</th>
              <th className="px-4 py-3 text-left">系统答案</th>
              <th className="px-4 py-3 text-left">相似度</th>
              <th className="px-4 py-3 text-left">来源</th>
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
                <td className="whitespace-pre-wrap px-4 py-3 text-gray-200">{row.question}</td>
                <td className="whitespace-pre-wrap px-4 py-3 text-gray-400">{row.expected_answer}</td>
                <td className="whitespace-pre-wrap px-4 py-3 text-gray-300">{row.actual_answer}</td>
                <td className="px-4 py-3 text-gray-400">{row.similarity.toFixed(4)}</td>
                <td className="px-4 py-3 text-gray-500">{row.source_refs.join(", ") || "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-gray-500">
                  暂无结果
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
