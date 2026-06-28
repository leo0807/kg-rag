"use client";
import { useEffect, useState } from "react";
import { CreditCard, Package } from "lucide-react";
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

const STATUS_LABEL: Record<string, string> = { pending: "待支付", paid: "已支付", overdue: "已逾期" };
const STATUS_CLS: Record<string, string>   = {
  pending: "text-yellow-400 bg-yellow-400/10 border-yellow-400/20",
  paid:    "text-green-400  bg-green-400/10  border-green-400/20",
  overdue: "text-red-400    bg-red-400/10    border-red-400/20",
};

export default function BillingPage() {
  const [bills, setBills]   = useState<Bill[]>([]);
  const [plans, setPlans]   = useState<Plan[]>([]);
  const [tab, setTab]       = useState<"bills" | "plans">("bills");
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

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
      setBills(prev => prev.map(b => b.id === id ? { ...b, status: "paid" } : b));
    } catch { /* ignore */ }
  };

  if (loading) return <div className="p-8 text-gray-400 text-sm">加载中…</div>;
  if (error) return (
    <div className="p-8 flex flex-col items-center gap-3 text-center">
      <div className="text-4xl">🔒</div>
      <div className="text-red-400 font-medium">{error}</div>
      <p className="text-gray-500 text-sm">请联系平台管理员获取相应权限</p>
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 blur-in">
        <div className="w-9 h-9 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
          <CreditCard size={16} className="text-blue-400" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-white">账单中心</h1>
          <p className="text-gray-400 text-sm mt-0.5">账单记录与套餐信息</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800">
        {([["bills", "账单记录", CreditCard], ["plans", "套餐详情", Package]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm border-b-2 transition-colors ${
              tab === key ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-white"
            }`}>
            <Icon size={13} />{label}
          </button>
        ))}
      </div>

      {/* Bills tab */}
      {tab === "bills" && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-800/80 text-gray-400 text-xs uppercase tracking-wider">
                  {["账期", "基础费用", "超量费用", "合计", "状态", "支付时间", "操作"].map(h => (
                    <th key={h} className="text-left px-4 py-3 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="animate-rows">
                {bills.map(b => (
                  <tr key={b.id} className="border-t border-gray-800 hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-3 text-white font-medium font-mono">{b.billing_period}</td>
                    <td className="px-4 py-3 text-gray-300">¥{b.base_amount}</td>
                    <td className="px-4 py-3 text-gray-300">¥{b.overage_amount}</td>
                    <td className="px-4 py-3 font-bold text-white">¥{b.total_amount}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_CLS[b.status] ?? "text-gray-400 bg-gray-800 border-gray-700"}`}>
                        {STATUS_LABEL[b.status] ?? b.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {b.paid_at ? new Date(b.paid_at).toLocaleDateString("zh-CN") : "—"}
                    </td>
                    <td className="px-4 py-3">
                      {b.status === "pending" && (
                        <button onClick={() => payBill(b.id)}
                          className="text-xs px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors">
                          标记已付
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {bills.length === 0 && (
            <div className="text-center text-gray-600 py-16 text-sm">暂无账单记录</div>
          )}
        </div>
      )}

      {/* Plans tab */}
      {tab === "plans" && (
        <>
          {plans.length === 0 ? (
            <div className="text-center text-gray-600 py-16 text-sm">暂无套餐数据</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 stagger-scale">
              {plans.map((p, i) => (
                <div key={p.name}
                  className={`relative bg-gray-900 border rounded-xl p-6 space-y-4 tech-card ${
                    i === 1 ? "border-blue-500/40" : "border-gray-800"
                  }`}>
                  {i === 1 && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] px-3 py-0.5 bg-blue-600 text-white rounded-full font-medium">
                      推荐
                    </div>
                  )}
                  <div>
                    <div className="text-white font-semibold text-base">{p.display_name}</div>
                    <div className="flex items-baseline gap-1 mt-2">
                      <span className="text-3xl font-bold text-white">¥{p.monthly_price_cny}</span>
                      <span className="text-gray-500 text-sm">/月</span>
                    </div>
                    {p.yearly_price_cny && (
                      <div className="text-xs text-green-400 mt-0.5">年付 ¥{p.yearly_price_cny}/月 · 省两个月</div>
                    )}
                  </div>
                  <div className="border-t border-gray-800 pt-4 space-y-2">
                    {[
                      ["最大用户数",   p.max_users            ? p.max_users.toLocaleString()                  : "无限制"],
                      ["最大文档数",   p.max_documents        ? p.max_documents.toLocaleString()              : "无限制"],
                      ["月查询配额",   p.max_queries_per_month ? p.max_queries_per_month.toLocaleString() + " 次" : "无限制"],
                    ].map(([label, val]) => (
                      <div key={label} className="flex items-center justify-between text-sm">
                        <span className="text-gray-500">{label}</span>
                        <span className="text-gray-200 font-medium">{val}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
