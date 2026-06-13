"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

type SimResult = {
  id: string; result_type: string; result_name: string;
  max_value?: number; min_value?: number; avg_value?: number;
  unit: string; pass_status: string;
};
type SimCase = {
  id: string; case_name: string; case_code?: string; description: string;
  domain: string; application: string; software: string; software_version: string;
  related_specs: string[]; related_sections: string[];
  inputs: Record<string, unknown>; outputs: Record<string, unknown>;
  images: string[]; project_code: string; confidence_level: string;
  created_at: string; updated_at: string;
};

import { fetchApi } from "@/lib/api";
const PASS_COLOR: Record<string, string> = {
  pass: "text-green-400", fail: "text-red-400", unknown: "text-gray-400"
};

export default function SimulationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [cas, setCas]         = useState<SimCase | null>(null);
  const [results, setResults] = useState<SimResult[]>([]);
  const [images, setImages]   = useState<string[]>([]);
  const [tab, setTab]         = useState<"info" | "results" | "images">("info");

  useEffect(() => {
    if (!id) return;
    fetchApi<SimCase>(`/api/simulation/cases/${id}`).then(setCas).catch(() => {});
    fetchApi<SimResult[]>(`/api/simulation/cases/${id}/results`).then(setResults).catch(() => {});
    fetchApi<{ images: string[] }>(`/api/simulation/cases/${id}/images`)
      .then(d => setImages(d.images ?? [])).catch(() => {});
  }, [id]);

  if (!cas) return <div className="p-6 text-gray-400 animate-pulse">加载中…</div>;

  return (
    <div className="p-6 max-w-5xl space-y-5">
      {/* Back + header */}
      <div className="flex items-center gap-3">
        <Link href="/simulation" className="text-gray-400 hover:text-white text-sm">← 返回</Link>
        <span className="text-gray-600">/</span>
        <h1 className="text-white font-semibold">{cas.case_name}</h1>
        {cas.case_code && <span className="text-gray-500 font-mono text-sm">{cas.case_code}</span>}
        <span className={`ml-auto text-xs px-2 py-0.5 rounded ${
          cas.confidence_level === "已验证" ? "bg-green-900 text-green-300" :
          cas.confidence_level === "参考"   ? "bg-blue-900 text-blue-300" :
          "bg-yellow-900 text-yellow-300"
        }`}>{cas.confidence_level}</span>
      </div>

      {/* Meta badges */}
      <div className="flex gap-2 flex-wrap">
        {[cas.domain, cas.application, cas.software, cas.software_version].filter(Boolean).map((t, i) => (
          <span key={i} className="text-xs bg-gray-800 text-gray-300 px-2 py-1 rounded">{t}</span>
        ))}
        {cas.project_code && (
          <span className="text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded">项目: {cas.project_code}</span>
        )}
      </div>

      {cas.description && <p className="text-gray-400 text-sm">{cas.description}</p>}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800">
        {(["info", "results", "images"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${tab === t ? "text-white border-b-2 border-blue-500" : "text-gray-400 hover:text-white"}`}>
            {t === "info" ? "输入参数" : t === "results" ? `结果 (${results.length})` : `云图 (${images.length})`}
          </button>
        ))}
      </div>

      {/* Tab: info */}
      {tab === "info" && (
        <div className="space-y-4">
          {/* Related specs */}
          {cas.related_specs.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <h3 className="text-white text-sm font-medium mb-2">关联规范</h3>
              <div className="flex gap-2 flex-wrap">
                {cas.related_specs.map((s, i) => (
                  <span key={i} className="text-xs bg-blue-900 text-blue-300 px-2 py-1 rounded">{s}</span>
                ))}
              </div>
            </div>
          )}
          {/* Inputs */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-white text-sm font-medium mb-3">输入条件</h3>
            <table className="w-full text-sm">
              <tbody>
                {Object.entries(cas.inputs).map(([k, v]) => (
                  <tr key={k} className="border-t border-gray-800">
                    <td className="py-2 pr-4 text-gray-400 w-1/3">{k}</td>
                    <td className="py-2 text-white">{String(v)}</td>
                  </tr>
                ))}
                {Object.keys(cas.inputs).length === 0 && (
                  <tr><td colSpan={2} className="text-gray-500 py-2">暂无输入数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab: results */}
      {tab === "results" && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-800 text-gray-400">
                <th className="px-4 py-2 text-left">结果名称</th>
                <th className="px-4 py-2 text-left">类型</th>
                <th className="px-4 py-2 text-right">最大值</th>
                <th className="px-4 py-2 text-right">最小值</th>
                <th className="px-4 py-2 text-right">均值</th>
                <th className="px-4 py-2 text-left">单位</th>
                <th className="px-4 py-2 text-left">状态</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => (
                <tr key={r.id} className="border-t border-gray-800">
                  <td className="px-4 py-2 text-white">{r.result_name}</td>
                  <td className="px-4 py-2 text-gray-400">{r.result_type}</td>
                  <td className="px-4 py-2 text-right text-white">{r.max_value ?? "—"}</td>
                  <td className="px-4 py-2 text-right text-white">{r.min_value ?? "—"}</td>
                  <td className="px-4 py-2 text-right text-white">{r.avg_value ?? "—"}</td>
                  <td className="px-4 py-2 text-gray-400">{r.unit}</td>
                  <td className={`px-4 py-2 ${PASS_COLOR[r.pass_status]}`}>{r.pass_status}</td>
                </tr>
              ))}
              {results.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-6 text-gray-500 text-center">暂无结果数据</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab: images */}
      {tab === "images" && (
        <div>
          {images.length === 0 ? (
            <p className="text-gray-500 text-center py-10">暂无云图文件</p>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              {images.map((src, i) => (
                <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
                  <img src={src} alt={`云图 ${i+1}`} className="w-full object-contain max-h-64" />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
