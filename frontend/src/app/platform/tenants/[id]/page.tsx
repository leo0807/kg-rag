import TenantDetail from "@/components/platform/TenantDetail";

export default function TenantDetailPage({ params }: { params: { id: string } }) {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-white">租户详情</h1>
      </div>
      <TenantDetail tenantId={params.id} />
    </div>
  );
}
