"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import TenantForm from "./TenantForm";

type Tenant = {
  id: string; name: string; slug: string; status: string; plan: string;
  contact_name: string | null; contact_email: string | null; contact_phone: string | null;
  trial_ends_at: string | null; subscription_ends_at: string | null;
  created_at: string; settings: Record<string, unknown>;
};

export default function TenantDetail({ tenantId }: { tenantId: string }) {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [tab, setTab] = useState<"info" | "edit">("info");
  const [extending, setExtending] = useState(false);

  const load = () =>
    fetchApi<Tenant>(`/api/platform/tenants/${tenantId}`).then(setTenant);

  useEffect(() => { load(); }, [tenantId]);

  const extendDays = async (days: number) => {
    setExtending(true);
    await fetchApi(`/api/platform/tenants/${tenantId}/extend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days }),
    });
    await load();
    setExtending(false);
  };

  if (!tenant) return <div className="text-gray-400 p-8">加载中…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <h2 className="text-xl font-semibold text-white">{tenant.name}</h2>
        <span className="text-gray-400 font-mono text-sm">/{tenant.slug}</span>
        <span className={`px-2 py-0.5 rounded text-xs ${
          tenant.status === "active" ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}>
          {tenant.status}
        </span>
      </div>

      <div className="flex gap-2 border-b border-gray-700">
        {(["info", "edit"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${tab === t ? "border-b-2 border-blue-500 text-white" : "text-gray-400 hover:text-white"}`}>
            {t === "info" ? "基本信息" : "编辑"}
          </button>
        ))}
      </div>

      {tab === "info" && (
        <div className="grid grid-cols-2 gap-6">
          <InfoCard label="套餐" value={tenant.plan} />
          <InfoCard label="联系人" value={tenant.contact_name ?? "—"} />
          <InfoCard label="联系邮箱" value={tenant.contact_email ?? "—"} />
          <InfoCard label="联系电话" value={tenant.contact_phone ?? "—"} />
          <InfoCard label="订阅到期" value={tenant.subscription_ends_at?.slice(0, 10) ?? "无限制"} />
          <InfoCard label="创建时间" value={tenant.created_at.slice(0, 10)} />

          <div className="col-span-2 pt-2 space-x-3">
            <span className="text-sm text-gray-400">续期：</span>
            {[30, 90, 365].map((d) => (
              <button key={d} onClick={() => extendDays(d)} disabled={extending}
                className="bg-blue-900 hover:bg-blue-800 disabled:opacity-50 text-blue-200 text-sm px-3 py-1 rounded">
                +{d}天
              </button>
            ))}
          </div>
        </div>
      )}

      {tab === "edit" && (
        <TenantForm
          tenantId={tenantId}
          initialData={{ ...tenant, contact_name: tenant.contact_name ?? "", contact_email: tenant.contact_email ?? "", contact_phone: tenant.contact_phone ?? "" }}
          onSuccess={() => { load(); setTab("info"); }}
        />
      )}
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-white text-sm">{value}</div>
    </div>
  );
}
