"use client";
import { useState } from "react";
import Link from "next/link";

type SimCase = {
  id: string; case_name: string; case_code?: string; domain: string;
  application: string; software: string; confidence_level: string;
  related_specs: string[]; inputs_summary: Record<string, unknown>;
};

const AUTH = () => `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") : ""}`;
const DOMAINS = ["", "structural", "thermal", "fluid", "coupled"];
const DOMAIN_CN: Record<string, string> = { "": "全部", structural: "结构", thermal: "热", fluid: "流体", coupled: "耦合" };

export default function SimSearchPage() {
  const [domain,    setDomain]    = useState("");
  const [app,       setApp]       = useState("");
  const [software,  setSoftware]  = useState("");
  const [material,  setMaterial]  = useState("");
  const [loadType,  setLoadType]  = useState("");
  const [tempMin,   setTempMin]   = useState("");
  const [tempMax,   setTempMax]   = useState("");
  const [presMin,   setPresMin]   = useState("");
  const [presMax,   setPresMax]   = useState("");
  const [conf,      setConf]      = useState("");
  const [results,   setResults]   = useState<SimCase[]>([]);
  const [loading,   setLoading]   = useState(false);
  const [searched,  setSearched]  = useState(false);

  const handleSearch = async () => {
    setLoading(true);
    setSearched(true);
    const body: Record<string, unknown> = {};
    if (domain)   body.domain = domain;
    if (app)      body.application = app;
    if (software) body.software = software;
    if (material) body.material = material;
    if (loadType) body.load_type = loadType;
    if (conf)     body.confidence_level = conf;
    if (tempMin && tempMax) body.temperature_range = [parseFloat(tempMin), parseFloat(tempMax)];
    if (presMin && presMax) body.pressure_range    = [parseFloat(presMin), parseFloat(presMax)];
    try {
      const r = await fetch("/api/simulation/search", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: AUTH() },
        body: JSON.stringify(body),
      });
      if (r.ok) setResults(await r.json());
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-white">参数化检索</h1>
        <p className="text-gray-400 text-sm mt-1">按物理参数精确查找仿真案例</p>
      </div>

      {/* Filter panel */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 space-y-4">
        {/* Row 1: domain + app + software */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-gray-400 text-xs mb-1 block">物理域</label>
            <select value={domain} onChange={e => setDomain(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm">
              {DOMAINS.map(d => <option key={d} value={d}>{DOMAIN_CN[d]}</option>)}
            </select>
          </div>
          <div>
            <label className="text-gray-400 text-xs mb-1 block">应用场景</label>
            <input value={app} onChange={e => setApp(e.target.value)}
              placeholder="密封 / 装配 / 焊接…"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm placeholder-gray-600" />
          </div>
          <div>
            <label className="text-gray-400 text-xs mb-1 block">仿真软件</label>
            <input value={software} onChange={e => setSoftware(e.target.value)}
              placeholder="abaqus / ansys…"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm placeholder-gray-600" />
          </div>
        </div>

        {/* Row 2: material + load + confidence */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-gray-400 text-xs mb-1 block">材料</label>
            <input value={material} onChange={e => setMaterial(e.target.value)}
              placeholder="Ti-6Al-4V / 304…"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm placeholder-gray-600" />
          </div>
          <div>
            <label className="text-gray-400 text-xs mb-1 block">载荷类型</label>
            <input value={loadType} onChange={e => setLoadType(e.target.value)}
              placeholder="疲劳 / 静载荷…"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm placeholder-gray-600" />
          </div>
          <div>
            <label className="text-gray-400 text-xs mb-1 block">可信度</label>
            <select value={conf} onChange={e => setConf(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm">
              <option value="">全部</option>
              <option value="已验证">已验证</option>
              <option value="参考">参考</option>
              <option value="初步">初步</option>
            </select>
          </div>
        </div>

        {/* Row 3: ranges */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-gray-400 text-xs mb-1 block">温度范围 (℃)</label>
            <div className="flex items-center gap-2">
              <input value={tempMin} onChange={e => setTempMin(e.target.value)}
                placeholder="最小"
                className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm placeholder-gray-600" />
              <span className="text-gray-500">~</span>
              <input value={tempMax} onChange={e => setTempMax(e.target.value)}
                placeholder="最大"
                className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm placeholder-gray-600" />
            </div>
          </div>
          <div>
            <label className="text-gray-400 text-xs mb-1 block">压力范围 (MPa)</label>
            <div className="flex items-center gap-2">
              <input value={presMin} onChange={e => setPresMin(e.target.value)}
                placeholder="最小"
                className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm placeholder-gray-600" />
              <span className="text-gray-500">~</span>
              <input value={presMax} onChange={e => setPresMax(e.target.value)}
                placeholder="最大"
                className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm placeholder-gray-600" />
            </div>
          </div>
        </div>

        <button onClick={handleSearch} disabled={loading}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded">
          {loading ? "检索中…" : "开始检索"}
        </button>
      </div>

      {/* Results */}
      {searched && (
        <div>
          <p className="text-gray-400 text-sm mb-3">找到 {results.length} 个匹配案例</p>
          <div className="space-y-2">
            {results.map(c => (
              <Link key={c.id} href={`/simulation/${c.id}`}
                className="flex items-center justify-between bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-lg px-4 py-3 transition-colors">
                <div>
                  <span className="text-white text-sm font-medium">{c.case_name}</span>
                  {c.case_code && <span className="text-gray-500 text-xs ml-2 font-mono">{c.case_code}</span>}
                  <div className="flex gap-2 mt-1">
                    {[c.domain, c.application, c.software].filter(Boolean).map((t, i) => (
                      <span key={i} className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">{t}</span>
                    ))}
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      c.confidence_level === "已验证" ? "bg-green-900 text-green-300" :
                      c.confidence_level === "参考"   ? "bg-blue-900 text-blue-300" :
                      "bg-yellow-900 text-yellow-300"}`}>
                      {c.confidence_level}
                    </span>
                  </div>
                </div>
                <span className="text-gray-600 text-xs">查看 →</span>
              </Link>
            ))}
            {results.length === 0 && (
              <div className="text-center text-gray-500 py-8">无匹配结果，请调整搜索条件</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
