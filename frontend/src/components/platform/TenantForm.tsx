"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

type Props = {
  initialData?: Partial<TenantFormData>;
  tenantId?: string;
  onSuccess?: () => void;
};

type TenantFormData = {
  name: string; slug: string; contact_name: string;
  contact_email: string; contact_phone: string;
  plan: string; status: string;
};

const PLANS = ["free", "standard", "enterprise"];
const STATUSES = ["active", "trial", "suspended", "expired"];

export default function TenantForm({ initialData, tenantId, onSuccess }: Props) {
  const router = useRouter();
  const isEdit = !!tenantId;

  const [form, setForm] = useState<TenantFormData>({
    name: "", slug: "", contact_name: "", contact_email: "",
    contact_phone: "", plan: "free", status: "active",
    ...initialData,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (key: keyof TenantFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const url = isEdit ? `/api/platform/tenants/${tenantId}` : "/api/platform/tenants";
      const res = await fetch(url, {
        method: isEdit ? "PUT" : "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail ?? "操作失败");
        return;
      }
      onSuccess ? onSuccess() : router.push("/platform/tenants");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-5 max-w-xl">
      {error && <div className="bg-red-900/40 border border-red-700 text-red-300 rounded px-4 py-2 text-sm">{error}</div>}

      <Field label="租户名称 *" required>
        <input className={INPUT} value={form.name} onChange={set("name")} required placeholder="例：ACME 航空" />
      </Field>
      <Field label="Slug *" required>
        <input className={INPUT} value={form.slug} onChange={set("slug")} required
          placeholder="例：acme（唯一标识，小写字母+数字）"
          disabled={isEdit}
        />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="套餐">
          <select className={INPUT} value={form.plan} onChange={set("plan")}>
            {PLANS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="状态">
          <select className={INPUT} value={form.status} onChange={set("status")}>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
      </div>
      <Field label="联系人">
        <input className={INPUT} value={form.contact_name} onChange={set("contact_name")} placeholder="联系人姓名" />
      </Field>
      <Field label="联系邮箱">
        <input className={INPUT} type="email" value={form.contact_email} onChange={set("contact_email")} placeholder="admin@acme.com" />
      </Field>
      <Field label="联系电话">
        <input className={INPUT} value={form.contact_phone} onChange={set("contact_phone")} placeholder="+86 138xxxx" />
      </Field>

      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={saving}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded text-sm">
          {saving ? "保存中…" : isEdit ? "更新租户" : "创建租户"}
        </button>
        <button type="button" onClick={() => router.back()}
          className="bg-gray-700 hover:bg-gray-600 text-white px-5 py-2 rounded text-sm">
          取消
        </button>
      </div>
    </form>
  );
}

const INPUT = "w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500";

function Field({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div>
      <label className="block text-sm text-gray-400 mb-1">{label}{required && <span className="text-red-400 ml-0.5">*</span>}</label>
      {children}
    </div>
  );
}
