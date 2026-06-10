"use client";
import { useEffect, useState } from "react";
import Link from "next/link";

type Tenant = {
  id: string; name: string; slug: string;
  status: string; plan: string;
  contact_email: string | null; created_at: string;
};

const STATUS_COLOR: Record<string, string> = {
  active: "text-green-400", suspended: "text-red-400",
  expired: "text-yellow-400", trial: "text-blue-400",
};

const PLAN_BADGE: Record<string, string> = {
  free: "bg-gray-700 text-gray-300", standard: "bg-blue-900 text-blue-200",
  enterprise: "bg-purple-900 text-purple-200",
};

export default function TenantList() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/api/platform/tenants", {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    })
      .then((r) => r.json())
      .then(setTenants)
      .finally(() => setLoading(false));
  }, []);

  const filtered = tenants.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.slug.toLowerCase().includes(search.toLowerCase())
  );

  const action = async (id: string, act: string) => {
    await fetch(`/api/platform/tenants/${id}/${act}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    });
    setTenants((prev) =>
      prev.map((t) =>
        t.id === id
          ? { ...t, status: act === "suspend" ? "suspended" : "active" }
          : t
      )
    );
  };

  if (loading) return <div className="text-gray-400 p-8">加载中…</div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <input
          className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white w-64"
          placeholder="搜索租户名称或 slug…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Link
          href="/platform/tenants/new"
          className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-1.5 rounded"
        >
          + 新建租户
        </Link>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400">
            <tr>
              {["名称", "Slug", "套餐", "状态", "联系邮箱", "创建时间", "操作"].map((h) => (
                <th key={h} className="text-left px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr key={t.id} className="border-t border-gray-800 hover:bg-gray-800/40">
                <td className="px-4 py-3">
                  <Link href={`/platform/tenants/${t.id}`} className="text-blue-400 hover:underline">
                    {t.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-gray-400 font-mono">{t.slug}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs ${PLAN_BADGE[t.plan] ?? "bg-gray-700 text-gray-300"}`}>
                    {t.plan}
                  </span>
                </td>
                <td className={`px-4 py-3 ${STATUS_COLOR[t.status] ?? "text-gray-400"}`}>{t.status}</td>
                <td className="px-4 py-3 text-gray-400">{t.contact_email ?? "—"}</td>
                <td className="px-4 py-3 text-gray-500">{t.created_at.slice(0, 10)}</td>
                <td className="px-4 py-3 space-x-2">
                  {t.status === "active" ? (
                    <button
                      onClick={() => action(t.id, "suspend")}
                      className="text-xs text-yellow-400 hover:underline"
                    >
                      暂停
                    </button>
                  ) : (
                    <button
                      onClick={() => action(t.id, "resume")}
                      className="text-xs text-green-400 hover:underline"
                    >
                      恢复
                    </button>
                  )}
                  <Link
                    href={`/platform/tenants/${t.id}`}
                    className="text-xs text-blue-400 hover:underline"
                  >
                    详情
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="text-center text-gray-500 py-12">暂无租户</div>
        )}
      </div>
      <div className="text-gray-500 text-xs">共 {filtered.length} 个租户</div>
    </div>
  );
}
