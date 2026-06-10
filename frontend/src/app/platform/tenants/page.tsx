import TenantList from "@/components/platform/TenantList";

export default function TenantsPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white">租户管理</h1>
        <p className="text-gray-400 text-sm mt-1">管理平台所有租户的订阅、配额和状态</p>
      </div>
      <TenantList />
    </div>
  );
}
