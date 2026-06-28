"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";

type SimCase = {
  id: string; case_name: string; case_code?: string; domain: string;
  application: string; software: string; confidence_level: string;
  related_specs: string[]; created_at: string;
};

const DOMAINS = ["", "structural", "thermal", "fluid", "coupled"];
const DOMAIN_LABEL: Record<string, string> = {
  "": "全部", structural: "结构", thermal: "热", fluid: "流体", coupled: "耦合"
};
const CONF_COLOR: Record<string, string> = {
  "已验证": "bg-green-900 text-green-300",
  "参考":   "bg-blue-900 text-blue-300",
  "初步":   "bg-yellow-900 text-yellow-300",
};

import { fetchApi } from "@/lib/api";

const EXAMPLE_CASES = [
  {
    case_name: "C919 主翼盒复合材料铺层结构强度验证",
    case_code: "SIM-STRUCT-2024-001",
    domain: "structural",
    application: "结构分析",
    software: "ABAQUS",
    confidence_level: "已验证",
    related_specs: ["CPS-CM-2201", "CPS-HY-0412"],
  },
  {
    case_name: "发动机吊架热应力分析（含热-结构耦合）",
    case_code: "SIM-COUPLED-2024-007",
    domain: "coupled",
    application: "热结构耦合",
    software: "ANSYS",
    confidence_level: "参考",
    related_specs: ["CPS-TH-0318"],
  },
  {
    case_name: "机翼前缘除冰系统气流场仿真",
    case_code: "SIM-FLUID-2024-012",
    domain: "fluid",
    application: "CFD 流场",
    software: "FLUENT",
    confidence_level: "初步",
    related_specs: ["CPS-FL-1102", "CPS-DE-0205"],
  },
];

function ExampleCaseGrid() {
  return (
    <div style={{ animation: "slide-up-fade 0.6s ease both" }}>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs text-gray-600 uppercase tracking-wider">示例案例（仅预览，新建后自动替换）</span>
        <div className="flex-1 h-px bg-gray-800" />
      </div>
      <div className="grid grid-cols-3 gap-4 stagger-children">
        {EXAMPLE_CASES.map((c, i) => (
          <div key={i} onClick={() => toast.info("这是示例数据，新建真实案例后将自动替换")}
            className="relative bg-gray-900/60 border border-gray-800/60 rounded-lg p-4 opacity-55 cursor-pointer hover:opacity-70 transition-opacity">
            <span className="absolute top-2.5 right-2.5 text-[9px] px-1.5 py-0.5 bg-gray-800 text-gray-600 rounded-full border border-gray-700">示例</span>
            <div className="flex items-start gap-2 mb-2 pr-10">
              <span className="text-white/70 font-medium text-sm line-clamp-2">{c.case_name}</span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs px-2 py-0.5 rounded ${CONF_COLOR[c.confidence_level] ?? "bg-gray-800 text-gray-400"}`}>
                {c.confidence_level}
              </span>
              <span className="text-gray-600 text-xs font-mono">{c.case_code}</span>
            </div>
            <div className="flex gap-2 flex-wrap">
              <span className="text-xs bg-gray-800/80 text-gray-400 px-2 py-0.5 rounded">{DOMAIN_LABEL[c.domain]}</span>
              <span className="text-xs bg-gray-800/80 text-gray-400 px-2 py-0.5 rounded">{c.application}</span>
              <span className="text-xs bg-gray-800/80 text-blue-400/60 px-2 py-0.5 rounded">{c.software}</span>
            </div>
            <p className="text-gray-600 text-xs mt-2">关联规范: {c.related_specs.join(", ")}</p>
          </div>
        ))}
      </div>
      <div className="flex justify-center mt-8">
        <Link href="/simulation/new"
          className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors">
          + 新建第一个仿真案例
        </Link>
      </div>
    </div>
  );
}

export default function SimulationPage() {
  const [cases, setCases]     = useState<SimCase[]>([]);
  const [domain, setDomain]   = useState("");
  const [q, setQ]             = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "50" });
    if (domain) params.set("domain", domain);
    if (q)      params.set("q", q);
    try {
      setCases(await fetchApi<SimCase[]>(`/api/simulation/cases?${params}`));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [domain]);

  const handleSearch = (e: React.FormEvent) => { e.preventDefault(); load(); };

  return (
    <div className="p-6 max-w-7xl space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white" style={{ animation: "slide-up-fade 0.55s ease both" }}>仿真案例库</h1>
          <p className="text-gray-400 text-sm mt-1">CAE/CFD 仿真结果管理与检索</p>
        </div>
        <Link href="/simulation/new"
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
          + 新建案例
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex gap-1">
          {DOMAINS.map(d => (
            <button key={d}
              onClick={() => setDomain(d)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                domain === d
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}>
              {DOMAIN_LABEL[d]}
            </button>
          ))}
        </div>
        <form onSubmit={handleSearch} className="flex gap-2 ml-auto">
          <input value={q} onChange={e => setQ(e.target.value)}
            placeholder="搜索案例名称…"
            className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-white placeholder-gray-500 w-56" />
          <button type="submit"
            className="px-3 py-1.5 bg-gray-700 text-white text-sm rounded hover:bg-gray-600">
            搜索
          </button>
        </form>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map(i => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 animate-pulse h-36" />
          ))}
        </div>
      ) : cases.length === 0 ? (
        <ExampleCaseGrid />
      ) : (
        <div className="grid grid-cols-3 gap-4 stagger-children">
          {cases.map(c => (
            <Link key={c.id} href={`/simulation/${c.id}`}
              className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-600 transition-colors block tech-card">
              <div className="flex items-start justify-between gap-2 mb-2">
                <span className="text-white font-medium text-sm line-clamp-2">{c.case_name}</span>
                <span className={`shrink-0 text-xs px-2 py-0.5 rounded ${CONF_COLOR[c.confidence_level] ?? "bg-gray-800 text-gray-400"}`}>
                  {c.confidence_level}
                </span>
              </div>
              {c.case_code && (
                <p className="text-gray-500 text-xs mb-2 font-mono">{c.case_code}</p>
              )}
              <div className="flex gap-2 flex-wrap">
                <span className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded">
                  {DOMAIN_LABEL[c.domain] ?? c.domain}
                </span>
                {c.application && (
                  <span className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded">
                    {c.application}
                  </span>
                )}
                {c.software && (
                  <span className="text-xs bg-gray-800 text-blue-300 px-2 py-0.5 rounded">
                    {c.software}
                  </span>
                )}
              </div>
              {c.related_specs.length > 0 && (
                <p className="text-gray-500 text-xs mt-2">关联规范: {c.related_specs.slice(0,2).join(", ")}{c.related_specs.length > 2 ? ` +${c.related_specs.length - 2}` : ""}</p>
              )}
              <p className="text-gray-600 text-xs mt-2">
                {c.created_at ? new Date(c.created_at).toLocaleDateString("zh-CN") : ""}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
