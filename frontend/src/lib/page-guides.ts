/**
 * 页面帮助内容数据文件
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
 * ────────────────────────────────────────────────────────────
 * 复杂路由组匹配样例（供 review 确认顺序正确性）
 * ────────────────────────────────────────────────────────────
 *
 * ▸ /library 组（父列表 + 动态详情）
 *   1. STRING  "/library"                     → 文档库列表
 *   2. REGEXP  /^\/library\/[^/]+$/           → /library/DOC-001（单个路径段）
 *   注：[doc_id] 只含一个段，[^/]+ 不会匹配多余的斜杠路径。
 *
 * ▸ /graph 组（两个静态路由，无动态段）
 *   1. STRING  "/graph"                       → 知识图谱
 *   2. STRING  "/graph/builder"               → 图谱构建器
 *   均为精确匹配，无需正则。
 *
 * ▸ /simulation 组（父 + 5 个静态子 + 1 个动态详情）
 *   1. STRING  "/simulation"                  → 仿真列表
 *   2. STRING  "/simulation/compare"          → 仿真对比
 *   3. STRING  "/simulation/dashboard"        → 仿真仪表盘
 *   4. STRING  "/simulation/search"           → 仿真搜索
 *   5. STRING  "/simulation/workflows"        → 仿真工作流
 *   6. REGEXP  /^\/simulation\/(?!compare$|dashboard$|search$|workflows$)[^/]+$/
 *              → /simulation/TASK-001（动态详情，排除已列举的静态子路由）
 *
 * ▸ /generation 组（父 + new + 动态详情 + 动态详情/edit）
 *   1. STRING  "/generation"                  → 生成列表
 *   2. STRING  "/generation/new"              → 新建生成
 *   3. REGEXP  /^\/generation\/[^/]+\/edit$/  → /generation/ID/edit（三段，最具体，优先）
 *   4. REGEXP  /^\/generation\/(?!new$)[^/]+$/→ /generation/ID（排除 new，单段）
 *   注：edit 的正则（三段）必须在详情正则（两段）之前；但因 edit 有三段而详情有两段，
 *       [^/]+ 本身就无法越段匹配，两者不会互相干扰——此处把 edit 放前只是防御性保序。
 *
 * ▸ /wiki 组（父列表 + 动态详情）
 *   1. STRING  "/wiki"                        → Wiki 首页
 *   2. REGEXP  /^\/wiki\/[^/]+$/             → /wiki/DOC-001
 *
 * ▸ /admin/eval 组（父 + 3 个静态子 + 动态 runs/[id]）
 *   1. STRING  "/admin/eval"                  → 评测中心
 *   2. STRING  "/admin/eval/datasets"         → 数据集管理
 *   3. STRING  "/admin/eval/compare"          → 评测对比
 *   4. STRING  "/admin/eval/trends"           → 评测趋势
 *   5. REGEXP  /^\/admin\/eval\/runs\/[^/]+$/ → /admin/eval/runs/RUN-001
 */

export type PageGuide = {
  /** 页面名称，显示在抽屉标题 */
  title: string;
  /** 一句话简介（30 字以内） */
  summary: string;
  /** 主要功能列表（3-5 条，基于页面实际 UI） */
  features: string[];
  /** 典型操作步骤（2-4 条） */
  actions: string[];
  /** 相关页面跳转链接（0-3 个） */
  related: { label: string; href: string }[];
};

export type GuideEntry = {
  /**
   * 路由匹配键：string 为精确匹配，RegExp 为模式匹配。
   * string 项必须全部排在 RegExp 项之前（见文件顶部说明）。
   */
  match: string | RegExp;
  /** 用于 localStorage 去重的稳定 key（动态路由用模板字符串表示） */
  key: string;
  guide: PageGuide;
};

// ─────────────────────────────────────────────────────────────────────────────
// 占位内容常量（Batch 0 阶段，Batch 1+ 逐步替换为真实文案）
// ─────────────────────────────────────────────────────────────────────────────
const TODO: PageGuide = {
  title: "页面帮助",
  summary: "功能介绍待补充。",
  features: [],
  actions: [],
  related: [],
};

// ─────────────────────────────────────────────────────────────────────────────
// PAGE_GUIDES：顺序敏感，string 精确匹配在前，RegExp 在后
// ─────────────────────────────────────────────────────────────────────────────
export const PAGE_GUIDES: GuideEntry[] = [
  // ══════════════════════════════════════════════
  // ① 所有 STRING 精确匹配项（按路由字母序排列）
  // ══════════════════════════════════════════════

  // ── 核心功能 ──
  { match: "/",                         key: "/",                         guide: TODO },
  { match: "/query",                    key: "/query",                    guide: TODO },
  { match: "/search",                   key: "/search",                   guide: TODO },
  { match: "/advanced-search",          key: "/advanced-search",          guide: TODO },
  { match: "/library",                  key: "/library",                  guide: TODO },
  { match: "/graph",                    key: "/graph",                    guide: TODO },
  { match: "/graph/builder",            key: "/graph/builder",            guide: TODO },
  { match: "/ingest",                   key: "/ingest",                   guide: TODO },
  { match: "/pipeline",                 key: "/pipeline",                 guide: TODO },
  { match: "/realtime",                 key: "/realtime",                 guide: TODO },

  // ── 内容工具 ──
  { match: "/references",               key: "/references",               guide: TODO },
  { match: "/favorites",                key: "/favorites",                guide: TODO },
  { match: "/notes",                    key: "/notes",                    guide: TODO },
  { match: "/compare",                  key: "/compare",                  guide: TODO },
  { match: "/timeline",                 key: "/timeline",                 guide: TODO },
  { match: "/wiki",                     key: "/wiki",                     guide: TODO },
  { match: "/cypher",                   key: "/cypher",                   guide: TODO },
  { match: "/analytics",                key: "/analytics",                guide: TODO },

  // ── 生成与通知（静态子路由先于动态正则）──
  { match: "/generation",               key: "/generation",               guide: TODO },
  { match: "/generation/new",           key: "/generation/new",           guide: TODO },

  // ── 用户与开发者 ──
  { match: "/settings",                 key: "/settings",                 guide: TODO },
  { match: "/developers",               key: "/developers",               guide: TODO },
  { match: "/notifications",            key: "/notifications",            guide: TODO },

  // ── 仿真（静态子路由先于动态正则）──
  { match: "/simulation",               key: "/simulation",               guide: TODO },
  { match: "/simulation/compare",       key: "/simulation/compare",       guide: TODO },
  { match: "/simulation/dashboard",     key: "/simulation/dashboard",     guide: TODO },
  { match: "/simulation/search",        key: "/simulation/search",        guide: TODO },
  { match: "/simulation/workflows",     key: "/simulation/workflows",     guide: TODO },

  // ── Platform ──
  { match: "/platform/dashboard",       key: "/platform/dashboard",       guide: TODO },
  { match: "/platform/tenants",         key: "/platform/tenants",         guide: TODO },
  { match: "/platform/tenants/new",     key: "/platform/tenants/new",     guide: TODO },
  { match: "/platform/usage",           key: "/platform/usage",           guide: TODO },

  // ── Admin — 运营 ──
  { match: "/admin/dashboard",          key: "/admin/dashboard",          guide: TODO },
  { match: "/admin/analytics",          key: "/admin/analytics",          guide: TODO },
  { match: "/admin/usage",              key: "/admin/usage",              guide: TODO },
  { match: "/admin/metrics",            key: "/admin/metrics",            guide: TODO },
  { match: "/admin/logs",               key: "/admin/logs",               guide: TODO },
  { match: "/admin/audit",              key: "/admin/audit",              guide: TODO },
  { match: "/admin/ops",                key: "/admin/ops",                guide: TODO },
  { match: "/admin/status",             key: "/admin/status",             guide: TODO },

  // ── Admin — 知识管理 ──
  { match: "/admin/ingest",             key: "/admin/ingest",             guide: TODO },
  { match: "/admin/entities",           key: "/admin/entities",           guide: TODO },
  { match: "/admin/associations",       key: "/admin/associations",       guide: TODO },
  { match: "/admin/conflicts",          key: "/admin/conflicts",          guide: TODO },
  { match: "/admin/synonyms",           key: "/admin/synonyms",           guide: TODO },
  { match: "/admin/annotation",         key: "/admin/annotation",         guide: TODO },
  { match: "/admin/schema",             key: "/admin/schema",             guide: TODO },
  { match: "/admin/governance",         key: "/admin/governance",         guide: TODO },
  { match: "/admin/lifecycle",          key: "/admin/lifecycle",          guide: TODO },
  { match: "/admin/data-quality",       key: "/admin/data-quality",       guide: TODO },
  { match: "/admin/processing",         key: "/admin/processing",         guide: TODO },

  // ── Admin — AI 与模型 ──
  { match: "/admin/gnn",                key: "/admin/gnn",                guide: TODO },
  { match: "/admin/finetune",           key: "/admin/finetune",           guide: TODO },
  { match: "/admin/local-models",       key: "/admin/local-models",       guide: TODO },
  { match: "/admin/prompts",            key: "/admin/prompts",            guide: TODO },
  { match: "/admin/lab",                key: "/admin/lab",                guide: TODO },
  { match: "/admin/ask-data",           key: "/admin/ask-data",           guide: TODO },
  { match: "/admin/cypher",             key: "/admin/cypher",             guide: TODO },

  // ── Admin — 评测（静态子路由先于动态正则）──
  { match: "/admin/eval",               key: "/admin/eval",               guide: TODO },
  { match: "/admin/eval/datasets",      key: "/admin/eval/datasets",      guide: TODO },
  { match: "/admin/eval/compare",       key: "/admin/eval/compare",       guide: TODO },
  { match: "/admin/eval/trends",        key: "/admin/eval/trends",        guide: TODO },

  // ── Admin — 安全与配置 ──
  { match: "/admin/compliance",         key: "/admin/compliance",         guide: TODO },
  { match: "/admin/credentials",        key: "/admin/credentials",        guide: TODO },
  { match: "/admin/integrations",       key: "/admin/integrations",       guide: TODO },
  { match: "/admin/webhooks",           key: "/admin/webhooks",           guide: TODO },
  { match: "/admin/permissions",        key: "/admin/permissions",        guide: TODO },
  { match: "/admin/billing",            key: "/admin/billing",            guide: TODO },
  { match: "/admin/quota",              key: "/admin/quota",              guide: TODO },
  { match: "/admin/tenant-settings",    key: "/admin/tenant-settings",    guide: TODO },
  { match: "/admin/feedback",           key: "/admin/feedback",           guide: TODO },

  // ── Admin — 报表 ──
  { match: "/admin/reports",            key: "/admin/reports",            guide: TODO },
  { match: "/admin/reports/new",        key: "/admin/reports/new",        guide: TODO },

  // ══════════════════════════════════════════════
  // ② 所有 RegExp 动态路由项（从上方所有 string 项之后开始）
  // ══════════════════════════════════════════════

  // /library/[doc_id]
  // 匹配 /library/任意单段，无需排除（没有其他静态子路由）
  {
    match: /^\/library\/[^/]+$/,
    key: "/library/[doc_id]",
    guide: TODO,
  },

  // /wiki/[doc_id]
  // 匹配 /wiki/任意单段
  {
    match: /^\/wiki\/[^/]+$/,
    key: "/wiki/[doc_id]",
    guide: TODO,
  },

  // /generation/[task_id]/edit（三段，比详情页更具体，放在详情页正则之前）
  {
    match: /^\/generation\/[^/]+\/edit$/,
    key: "/generation/[task_id]/edit",
    guide: TODO,
  },

  // /generation/[task_id]（排除 new；edit 因为有第三段 /edit 而不会被此正则命中）
  {
    match: /^\/generation\/(?!new$)[^/]+$/,
    key: "/generation/[task_id]",
    guide: TODO,
  },

  // /simulation/[id]（排除所有已列举的静态子路由）
  {
    match: /^\/simulation\/(?!compare$|dashboard$|search$|workflows$)[^/]+$/,
    key: "/simulation/[id]",
    guide: TODO,
  },

  // /platform/tenants/[id]（排除 new）
  {
    match: /^\/platform\/tenants\/(?!new$)[^/]+$/,
    key: "/platform/tenants/[id]",
    guide: TODO,
  },

  // /admin/audit/users/[id]
  {
    match: /^\/admin\/audit\/users\/[^/]+$/,
    key: "/admin/audit/users/[id]",
    guide: TODO,
  },

  // /admin/eval/runs/[id]
  {
    match: /^\/admin\/eval\/runs\/[^/]+$/,
    key: "/admin/eval/runs/[id]",
    guide: TODO,
  },

  // /shared/[token]
  {
    match: /^\/shared\/[^/]+$/,
    key: "/shared/[token]",
    guide: TODO,
  },
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
