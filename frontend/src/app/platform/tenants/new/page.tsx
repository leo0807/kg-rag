import TenantForm from "@/components/platform/TenantForm";

export default function NewTenantPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white">新建租户</h1>
        <p className="text-gray-400 text-sm mt-1">为新企业/部门创建独立租户</p>
      </div>
      <TenantForm />
    </div>
  );
}
