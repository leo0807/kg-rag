import { Activity } from "lucide-react";

export function StatCard({ label, value, sub, icon: Icon, warn }: {
  label: string; value: string | number; sub?: string;
  icon: typeof Activity; warn?: boolean;
}) {
  return (
    <div className={`bg-gray-900 border rounded-lg p-4 ${warn ? "border-amber-700" : "border-gray-800"}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon size={14} className={warn ? "text-amber-400" : "text-indigo-400"} />
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <div className={`text-xl font-semibold ${warn ? "text-amber-300" : "text-gray-100"}`}>{value}</div>
      {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
    </div>
  );
}
