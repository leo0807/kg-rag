"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo } from "react";
import { useCurrentUser } from "@/app/sidebar/useCurrentUser";
import { AdminCypherWorkbench } from "./AdminCypherWorkbench";
import { CypherBuilderWorkbench } from "./BuilderWorkbench";

type CypherTab = "builder" | "admin";

export default function CypherPage() {
  const user = useCurrentUser();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const isAdmin = user?.is_admin === true;
  const activeTab = useMemo<CypherTab>(() => {
    const raw = searchParams.get("tab");
    if (raw === "admin" && isAdmin) return "admin";
    return "builder";
  }, [searchParams, isAdmin]);

  useEffect(() => {
    if (!isAdmin && searchParams.get("tab") === "admin") {
      router.replace(`${pathname}?tab=builder`);
    }
  }, [isAdmin, pathname, router, searchParams]);

  function switchTab(tab: CypherTab) {
    if (tab === "admin" && !isAdmin) return;
    router.replace(`${pathname}?tab=${tab}`);
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-gray-950 text-gray-200">
      <div className="flex shrink-0 items-center justify-between border-b border-gray-800 px-4 py-3">
        <div>
          <h1 className="text-base font-semibold text-white">Cypher 工具</h1>
          <p className="text-xs text-gray-500">
            构造查询与执行查询合并为一个入口，通过标签页切换。
          </p>
        </div>
      </div>

      <div className="flex shrink-0 gap-2 border-b border-gray-800 px-4 pt-3">
        <TabButton
          active={activeTab === "builder"}
          onClick={() => switchTab("builder")}
        >
          Cypher 构造器
        </TabButton>
        {isAdmin && (
          <TabButton
            active={activeTab === "admin"}
            onClick={() => switchTab("admin")}
          >
            Cypher 执行器
          </TabButton>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-hidden">
        {activeTab === "builder" ? (
          <CypherBuilderWorkbench />
        ) : (
          <AdminCypherWorkbench />
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-t-xl border border-b-0 px-4 py-2 text-sm transition-colors ${
        active
          ? "border-indigo-500 bg-gray-900 text-white"
          : "border-gray-800 bg-gray-950 text-gray-500 hover:text-gray-200"
      }`}
    >
      {children}
    </button>
  );
}
