"use client";
import { useEffect, useState } from "react";
import { fetchApi, ApiError } from "@/lib/api";

type Bill = {
  id: string; billing_period: string; status: string;
  base_amount: string; overage_amount: string; total_amount: string;
  details: Record<string, unknown>; paid_at: string | null; created_at: string;
};

type Plan = {
  name: string; display_name: string; monthly_price_cny: string; yearly_price_cny: string;
  max_users: number | null; max_documents: number | null; max_queries_per_month: number | null;
};

const STATUS = { pending: "text-yellow-400", paid: "text-green-400", overdue: "text-red-400" };

export default function BillingPage() {
  const [bills, setBills] = useState<Bill[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [tab, setTab] = useState<"bills" | "plans">("bills");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchApi<Bill[]>("/api/admin/billing/bills"),
      fetchApi<Plan[]>("/api/admin/billing/plans"),
    ]).then(([b, p]) => {
      setBills(Array.isArray(b) ? b : []);
      setPlans(Array.isArray(p) ? p : []);
    }).catch((e) => {
      setError(e instanceof ApiError && e.status === 403 ? "无权限访问账单功能" : "加载失败，请刷新重试");
    }).finally(() => setLoading(false));
  }, []);

  const payBill = async (id: string) => {
    try {
      await fetchApi(`/api/admin/billing/bills/${id}/pay`, { method: "POST" });
      setBills((prev) => prev.map((b) => (b.id === id ? { ...b, status: "paid" } : b)));
    } catch { /* ignore */ }
  };

  if (loading) return <div className="p-8 text-gray-400">加载中…</div>;
  if (error) return (
    <div className="p-8 flex flex-col items-center gap-3 text-center">
      <div className="text-4xl">🔒</div>
      <div className="text-red-400 font-medium">{error}</div>
      <p className="text-gray-500 text-sm">请联系平台管理员获取相应权限</p>
    </div>
  );

  return (
    <div className="p-6 max-w-5xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white">账单中心</h1>
        <p className="text-gray-400 text-sm mt-1">账单记录与套餐信息</p>
      </div>

      <div className="flex gap-2 mb-6 border-b border-gray-700">
        {(["bills", "plans"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${tab === t ? "border-b-2 border-blue-500 text-white" : "text-gray-400 hover:text-white"}`}>
            {t === "bills" ? "账单记录" : "套餐详情"}
          </button>
        ))}
      </div>

      {tab === "bills" && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400">
              <tr>
                {["账期", "基础费用", "超量费用", "总计", "状态", "操作"].map((h) => (
                  <th key={h} className="text-left px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {bills.map((b) => (
                <tr key={b.id} className="border-t border-gray-800">
                  <td className="px-4 py-3 text-white">{b.billing_period}</td>
                  <td className="px-4 py-3 text-gray-300">¥{b.base_amount}</td>
                  <td className="px-4 py-3 text-gray-300">¥{b.overage_amount}</td>
                  <td className="px-4 py-3 font-semibold text-white">¥{b.total_amount}</td>
                  <td className={`px-4 py-3 ${STATUS[b.status as keyof typeof STATUS] ?? "text-gray-400"}`}>
                    {b.status}
                  </td>
                  <td className="px-4 py-3">
                    {b.status === "pending" && (
                      <button onClick={() => payBill(b.id)} className="text-xs text-blue-400 hover:underline">
                        标记已付
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {bills.length === 0 && <div className="text-center text-gray-500 py-12">暂无账单</div>}
        </div>
      )}

      {tab === "plans" && (
        <div className="grid grid-cols-3 gap-4">
          {plans.map((p) => (
            <div key={p.name} className="bg-gray-800 border border-gray-700 rounded-lg p-5 space-y-3">
              <div className="text-white font-semibold">{p.display_name}</div>
              <div className="text-2xl font-bold text-white">¥{p.monthly_price_cny}<span className="text-sm text-gray-400">/月</span></div>
              <div className="text-xs text-gray-500 space-y-1">
                <div>用户数: {p.max_users ?? "无限制"}</div>
                <div>文档数: {p.max_documents ?? "无限制"}</div>
                <div>月查询: {p.max_queries_per_month ? p.max_queries_per_month.toLocaleString() : "无限制"}</div>
              </div>
            </div>
          ))}
          {plans.length === 0 && <div className="col-span-3 text-center text-gray-500 py-12">暂无套餐数据</div>}
        </div>
      )}
    </div>
  );
}
