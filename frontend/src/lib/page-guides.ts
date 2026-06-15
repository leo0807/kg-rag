/**
 * 页面帮助内容入口文件（barrel）
 *
 * 路由匹配规则（必须遵守以下顺序和约束）：
 *
 * 1. PAGE_GUIDES 数组中，所有 string 精确匹配项必须排在所有 RegExp 项之前。
 *    这样精确路径永远优先于正则，不会被宽泛正则"吞掉"。
 *
 * 2. 动态段正则（如 /library/[doc_id]）必须用负向前瞻排除同前缀的静态子路由。
 *    示例：/simulation/[id] 的正则需排除 compare/dashboard/search/workflows
 *    → /^\/simulation\/(?!compare$|dashboard$|search$|workflows$)[^/]+$/
 *
 * 3. findGuide() 按数组顺序依次测试，第一个命中即返回，无需考虑后续项。
 *
 * 内容拆分到 guides/ 子目录各模块文件中，本文件仅做组装。
 * dynamicRouteGuides 必须最后合并，以保证 RegExp 项在 string 项之后。
 */

export type { PageGuide, GuideEntry } from "./guides/types";

import { coreGuides }           from "./guides/core";
import { contentGuides }        from "./guides/content";
import { generationGuides }     from "./guides/generation";
import { simulationGuides }     from "./guides/simulation";
import { platformGuides }       from "./guides/platform";
import { adminOpsGuides }       from "./guides/admin-ops";
import { adminKnowledgeGuides } from "./guides/admin-knowledge";
import { adminAiGuides }        from "./guides/admin-ai";
import { adminEvalGuides }      from "./guides/admin-eval";
import { adminSecurityGuides }  from "./guides/admin-security";
import { dynamicRouteGuides }   from "./guides/dynamic-routes";
import type { GuideEntry, PageGuide } from "./guides/types";

// ─────────────────────────────────────────────────────────────────────────────
// PAGE_GUIDES：顺序敏感
//   1. 所有 string 精确匹配（来自各模块子文件）
//   2. 所有 RegExp 动态路由（dynamicRouteGuides，必须最后合并）
// ─────────────────────────────────────────────────────────────────────────────
export const PAGE_GUIDES: GuideEntry[] = [
  ...coreGuides,            // /, /query, /search, /advanced-search, /library, /graph, /graph/builder, /ingest, /pipeline, /realtime
  ...contentGuides,         // /references, /favorites, /notes, /compare, /timeline, /wiki, /cypher, /analytics
  ...generationGuides,      // /generation, /generation/new, /settings, /developers, /notifications
  ...simulationGuides,      // /simulation, /simulation/compare, /simulation/dashboard, /simulation/search, /simulation/workflows
  ...platformGuides,        // /platform/dashboard, /platform/tenants, /platform/tenants/new, /platform/usage
  ...adminOpsGuides,        // /admin/dashboard, /analytics, /usage, /metrics, /logs, /audit, /ops, /status
  ...adminKnowledgeGuides,  // /admin/ingest, /entities, /associations, /conflicts, /synonyms, /annotation, /schema, /governance, /lifecycle, /data-quality, /processing
  ...adminAiGuides,         // /admin/gnn, /finetune, /local-models, /prompts, /lab, /ask-data, /cypher
  ...adminEvalGuides,       // /admin/eval, /eval/datasets, /eval/compare, /eval/trends
  ...adminSecurityGuides,   // /admin/compliance, /credentials, /integrations, /webhooks, /permissions, /billing, /quota, /tenant-settings, /feedback, /reports, /reports/new
  ...dynamicRouteGuides,    // RegExp 动态路由（必须最后）: /library/[doc_id], /wiki/[doc_id], /generation/[id]/edit, /generation/[id], /simulation/[id], /platform/tenants/[id], /admin/audit/users/[id], /admin/eval/runs/[id], /shared/[token]
];

// ─────────────────────────────────────────────────────────────────────────────
// findGuide：按数组顺序匹配，第一个命中即返回
// ─────────────────────────────────────────────────────────────────────────────
export function findGuide(
  pathname: string
): { guide: PageGuide; key: string } | null {
  for (const entry of PAGE_GUIDES) {
    const matched =
      typeof entry.match === "string"
        ? pathname === entry.match
        : entry.match.test(pathname);
    if (matched) {
      return { guide: entry.guide, key: entry.key };
    }
  }
  return null;
}
