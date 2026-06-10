import QuotaPanel from "@/components/quota/QuotaPanel";

export default function QuotaPage() {
  return (
    <div className="p-6 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white">配额使用情况</h1>
        <p className="text-gray-400 text-sm mt-1">当前租户的资源使用与限额</p>
      </div>
      <QuotaPanel />
    </div>
  );
}
