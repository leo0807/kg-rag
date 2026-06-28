"use client";
import { useEffect, useState } from "react";
import { Database, FileText, MessageSquare, Users, Zap, CheckCircle2, XCircle } from "lucide-react";
import { fetchApi, ApiError } from "@/lib/api";

type QuotaItem = { used: number | null; limit: number | null; pct: number | null };
type UsageSummary = {
  period: string;
  queries: QuotaItem;
  tokens: QuotaItem;
  storage_mb: QuotaItem;
  users: QuotaItem;
  documents: QuotaItem;
  features: Record<string, boolean>;
};

const QUOTA_META = [
  { dataKey: "queries",    label: "查询次数",   unit: "次",  Icon: MessageSquare, bar: "from-blue-500 to-cyan-400",    ring: "border-blue-500/20",   bg: "bg-blue-500/8"   },
  { dataKey: "tokens",     label: "LLM Tokens", unit: "tok", Icon: Zap,           bar: "from-violet-500 to-purple-400", ring: "border-violet-500/20", bg: "bg-violet-500/8" },
  { dataKey: "storage_mb", label: "存储空间",   unit: "MB",  Icon: Database,      bar: "from-teal-500 to-emerald-400", ring: "border-teal-500/20",   bg: "bg-teal-500/8"   },
  { dataKey: "users",      label: "用户数",     unit: "人",  Icon: Users,         bar: "from-amber-500 to-orange-400", ring: "border-amber-500/20",  bg: "bg-amber-500/8"  },
  { dataKey: "documents",  label: "文档数",     unit: "份",  Icon: FileText,      bar: "from-rose-500 to-pink-400",   ring: "border-rose-500/20",   bg: "bg-rose-500/8"   },
] as const;

function pctColor(pct: number | null) {
  if (pct == null) return "text-gray-500";
  if (pct >= 90) return "text-red-400";
  if (pct >= 70) return "text-yellow-400";
  return "text-green-400";
}

function barColor(pct: number | null) {
  if (pct == null) return "from-gray-600 to-gray-500";
  if (pct >= 90) return "from-red-500 to-rose-400";
  if (pct >= 70) return "from-yellow-500 to-amber-400";
  return null; // use meta color
}

function fmt(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function QuotaCard({
  label, unit, Icon, bar, ring, bg, item, idx,
}: Omit<(typeof QUOTA_META)[number], "dataKey"> & { item: QuotaItem; idx: number }) {
  const pct = item.pct ?? 0;
  const themeBar = barColor(item.pct) ?? bar;

  return (
    <div
      className={`rounded-xl border ${ring} ${bg} p-5 flex flex-col gap-4 tech-card`}
      style={{ animation: `scale-fade 0.45s cubic-bezier(0.34,1.56,0.64,1) both ${idx * 80}ms` }}
    >
      {/* Top row */}
      <div className="flex items-start justify-between">
        <div className={`w-9 h-9 rounded-lg ${bg} border ${ring} flex items-center justify-center shrink-0`}>
          <Icon size={16} className={pctColor(item.pct)} />
        </div>
        <span className={`text-xl font-bold tabular-nums ${pctColor(item.pct)}`}>
          {item.pct != null ? `${item.pct}%` : "∞"}
        </span>
      </div>

      {/* Label + numbers */}
      <div>
        <p className="text-xs text-gray-500 mb-1">{label}</p>
        <p className="text-sm text-white font-medium tabular-nums">
          {fmt(item.used)}{" "}
          <span className="text-gray-500 font-normal">/ {item.limit != null ? fmt(item.limit) : "无限制"} {unit}</span>
        </p>
      </div>

      {/* Progress bar */}
      <div>
        <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${themeBar} transition-all duration-1000`}
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
        {pct >= 70 && (
          <p className="text-[10px] mt-1 text-right" style={{ color: pct >= 90 ? "#f87171" : "#facc15" }}>
            {pct >= 90 ? "⚠ 即将达到上限" : "接近限额"}
          </p>
        )}
      </div>
    </div>
  );
}

export default function QuotaPanel() {
  const [data, setData]     = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    fetchApi<UsageSummary>("/api/admin/quota")
      .then(setData)
      .catch((e) => {
        setError(e instanceof ApiError && e.status === 403 ? "无权限查看配额" : "配额数据加载失败");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="h-44 rounded-xl bg-gray-900 animate-pulse" />
      ))}
    </div>
  );
  if (error) return (
    <div className="flex flex-col items-center gap-3 py-20 text-center">
      <div className="text-4xl">🔒</div>
      <p className="text-red-400 text-sm font-medium">{error}</p>
    </div>
  );
  if (!data) return (
    <div className="text-gray-500 text-sm py-12 text-center">无法获取配额信息</div>
  );

  const featureEntries = Object.entries(data.features ?? {});

  return (
    <div className="space-y-6">
      {/* Resource cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {QUOTA_META.map((meta, idx) => (
          <QuotaCard
            key={meta.dataKey}
            label={meta.label}
            unit={meta.unit}
            Icon={meta.Icon}
            bar={meta.bar}
            ring={meta.ring}
            bg={meta.bg}
            item={data[meta.dataKey]}
            idx={idx}
          />
        ))}
      </div>

      {/* Feature flags */}
      {featureEntries.length > 0 && (
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-5"
          style={{ animation: "slide-up-fade 0.5s ease both 450ms" }}>
          <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4">功能开关</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
            {featureEntries.map(([key, enabled]) => (
              <div key={key} className="flex items-center gap-2 text-sm">
                {enabled
                  ? <CheckCircle2 size={13} className="text-green-400 shrink-0" />
                  : <XCircle     size={13} className="text-gray-600 shrink-0" />}
                <span className={enabled ? "text-gray-200" : "text-gray-600"}>{key}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
