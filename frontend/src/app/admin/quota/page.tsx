import { BarChart3 } from "lucide-react";
import QuotaPanel from "@/components/quota/QuotaPanel";

export default function QuotaPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3" style={{ animation: "blur-fade 0.55s ease both" }}>
        <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
          <BarChart3 size={16} className="text-indigo-400" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-white">配额使用情况</h1>
          <p className="text-gray-400 text-sm mt-0.5">当前租户的资源使用与限额</p>
        </div>
      </div>
      <QuotaPanel />
    </div>
  );
}
