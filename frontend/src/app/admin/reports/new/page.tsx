"use client";
import { useRouter } from "next/navigation";
import { ReportBuilder } from "../ReportBuilder";
import type { WidgetConfig } from "../PropertyPanel";

const AUTH = () => `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") : ""}`;

export default function NewReportPage() {
  const router = useRouter();

  const save = async (name: string, widgets: WidgetConfig[]) => {
    const r = await fetch("/api/admin/reports", {
      method: "POST",
      headers: { Authorization: AUTH(), "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        config: widgets,
        layout: { columns: 2 },
      }),
    });
    if (r.ok) router.push("/admin/reports");
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col">
      <div className="px-6 py-3 bg-gray-950 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <button onClick={() => router.back()} className="text-gray-400 hover:text-white text-sm">← 返回</button>
          <h1 className="text-white font-medium">新建报表</h1>
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        <ReportBuilder onSave={save} />
      </div>
    </div>
  );
}
