/**
 * J1.3: Declarative chart DSL — schema, validation, and renderer selection.
 */
import type { DataSourceConfig } from "./datasource";

export type ChartType =
  | "line" | "bar" | "pie" | "area" | "scatter"
  | "radar" | "heatmap" | "gauge" | "treemap" | "timeline";

export type DSLDataConfig = {
  source: "api" | "ws" | "sse" | "static";
  endpoint?: string;
  refresh_interval?: number;  // ms
  static_data?: Record<string, unknown>[];
};

export type DSLAxis = {
  key: string;
  label?: string;
  unit?: string;
};

export type DSLOptions = {
  legend?: boolean;
  stacked?: boolean;
  smooth?: boolean;
  donut?: boolean;
  horizontal?: boolean;
  height?: number;
  thresholds?: [number, number];
};

export type ChartDSL = {
  type: ChartType;
  title?: string;
  data: DSLDataConfig;
  x?: string;              // x-axis key
  y?: string | string[];   // y-axis key(s)
  options?: DSLOptions;
  id?: string;
};

export type DashboardDSL = {
  id: string;
  title: string;
  description?: string;
  layout: "grid" | "flex";
  columns?: number;
  charts: ChartDSL[];
};

// ── Converters ────────────────────────────────────────────────────────────────

export function dslToDataSourceConfig(dsl: DSLDataConfig): DataSourceConfig {
  if (dsl.source === "static") {
    return { type: "static", data: dsl.static_data ?? [] };
  }
  if (dsl.source === "ws") {
    return { type: "ws", url: dsl.endpoint ?? "" };
  }
  if (dsl.source === "sse") {
    return { type: "sse", url: dsl.endpoint ?? "" };
  }
  return {
    type: "api",
    endpoint: dsl.endpoint ?? "",
    refresh_interval: dsl.refresh_interval,
  };
}

export function getYKeys(dsl: ChartDSL): string[] {
  if (!dsl.y) return [];
  return Array.isArray(dsl.y) ? dsl.y : [dsl.y];
}

// ── Validation ────────────────────────────────────────────────────────────────

export type ValidationError = { field: string; message: string };

export function validateDSL(dsl: ChartDSL): ValidationError[] {
  const errors: ValidationError[] = [];
  if (!dsl.type) errors.push({ field: "type", message: "图表类型必填" });
  if (!dsl.data?.source) errors.push({ field: "data.source", message: "数据源必填" });
  if (dsl.data?.source === "api" && !dsl.data.endpoint) {
    errors.push({ field: "data.endpoint", message: "API 端点必填" });
  }
  if (["line", "bar", "area", "scatter"].includes(dsl.type) && !dsl.x) {
    errors.push({ field: "x", message: `${dsl.type} 图需要 x 轴` });
  }
  if (["line", "bar", "area"].includes(dsl.type) && !dsl.y) {
    errors.push({ field: "y", message: `${dsl.type} 图需要 y 轴` });
  }
  return errors;
}

// ── Presets ───────────────────────────────────────────────────────────────────

export const PRESET_DSLS: Record<string, ChartDSL> = {
  query_trend: {
    type: "line",
    title: "查询量趋势",
    data: { source: "api", endpoint: "/api/metrics/queries", refresh_interval: 60_000 },
    x: "date", y: ["queries", "errors"],
    options: { smooth: true, legend: true },
  },
  user_activity: {
    type: "bar",
    title: "用户活跃度",
    data: { source: "api", endpoint: "/api/metrics/users" },
    x: "date", y: ["active_users"],
    options: {},
  },
  answer_quality: {
    type: "area",
    title: "答案质量趋势",
    data: { source: "api", endpoint: "/api/metrics/quality" },
    x: "date", y: ["avg_score"],
    options: { smooth: true },
  },
};

export function parseDSL(json: string): ChartDSL {
  const dsl = JSON.parse(json) as ChartDSL;
  const errs = validateDSL(dsl);
  if (errs.length) throw new Error(errs.map(e => e.message).join("; "));
  return dsl;
}
