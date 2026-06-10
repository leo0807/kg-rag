import UsageChart from "@/components/quota/UsageChart";

export default function PlatformUsagePage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white">全平台用量</h1>
        <p className="text-gray-400 text-sm mt-1">所有租户当月资源使用概览</p>
      </div>
      <UsageChart />
    </div>
  );
}
