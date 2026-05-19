"use client";

import { useEffect } from "react";
import {
  type NodeType,
  type RelDir,
  type RelType,
  useCypherBuilder,
} from "../admin/cypher/useCypherBuilder";
import { useCurrentUser } from "../sidebar/useCurrentUser";
import { AdminCypherForm } from "./AdminCypherForm";
import { AdminCypherResultPanel } from "./AdminCypherResultPanel";

export function AdminCypherWorkbench() {
  const user = useCurrentUser();
  const builder = useCypherBuilder();

  useEffect(() => {
    builder.buildCypher();
  }, [builder.buildCypher]);

  if (!user?.is_admin) {
    return (
      <div className="flex h-full items-start justify-center bg-gray-950 p-8 text-sm text-red-400">
        权限不足，仅管理员可访问
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-gray-950">
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <AdminCypherForm
          nodeType={builder.nodeType as NodeType}
          setNodeType={builder.setNodeType}
          propKey={builder.propKey}
          setPropKey={builder.setPropKey}
          propVal={builder.propVal}
          setPropVal={builder.setPropVal}
          relType={builder.relType as RelType}
          setRelType={builder.setRelType}
          relDir={builder.relDir as RelDir}
          setRelDir={builder.setRelDir}
          targetType={builder.targetType}
          setTargetType={builder.setTargetType}
          limitVal={builder.limitVal}
          setLimitVal={builder.setLimitVal}
          orderBy={builder.orderBy}
          setOrderBy={builder.setOrderBy}
          buildCypher={builder.buildCypher}
          applyTemplate={builder.applyTemplate}
        />

        <AdminCypherResultPanel
          cypher={builder.cypher}
          setCypher={builder.setCypher}
          running={builder.running}
          result={builder.result}
          execute={builder.execute}
        />
      </div>
    </div>
  );
}
