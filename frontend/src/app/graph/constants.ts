export interface GraphNode {
    id:           string;
    label:        string;
    name:         string;
    type?:        string;
    doc_id?:      string;
    description?: string;
    content?:     string;
    path?:        string;
    url?:         string;
    is_drawing?:  boolean;
    row_count?:   number;
    level?:       number;
    number?:      string;
    has_children?: boolean;
    x?:           number;
    y?:           number;
}

export interface GraphEdge {
    source: string | GraphNode;
    target: string | GraphNode;
    type:   string;
}

export interface GraphStats {
    total:    number;
    docs:     number;
    sections: number;
    images:   number;
    tables:   number;
    entities: number;
}

export interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
    stats?: GraphStats;
}

export interface SimNode extends GraphNode {
    fx?: number | null;
    fy?: number | null;
}

export interface TourStop {
    index:       number;
    node_id:     string;
    node:        GraphNode;
    explanation: string;
}

export interface Limits {
    doc:          number;
    sec:          number;
    entity:       number;
    tbl:          number;
    show_level:   number;   // 0 = all, 1-4 = depth
    show_images:  boolean;
    show_entities: boolean;
}

export const MIN_SCALE = 0.1;
export const MAX_SCALE = 4;

export const NODE_COLOR: Record<string, string> = {
    Document:   "#6366f1",
    Section:    "#f59e0b",
    Image:      "#ec4899",
    Tool:       "#10b981",
    Material:   "#f97316",
    Process:    "#a78bfa",
    Constraint: "#ef4444",
    Table:      "#22c55e",
};

export const NODE_SHORT: Record<string, string> = {
    "全部":     "全部",
    Document:   "文档",
    Section:    "章节",
    Image:      "图片",
    Tool:       "工具",
    Material:   "材料",
    Process:    "工序",
    Constraint: "约束",
    Table:      "表格",
};

export const EDGE_COLOR: Record<string, string> = {
    HAS_SECTION:      "#4f46e5",
    REFERENCES:       "#059669",
    HAS_SUBSECTION:   "#d97706",
    NEXT_SECTION:     "#6b7280",
    HAS_IMAGE:        "#ec4899",
    HAS_TABLE:        "#22c55e",
    REQUIRES_TOOL:    "#10b981",
    USES_MATERIAL:    "#f97316",
    INVOLVES_PROCESS: "#a78bfa",
    HAS_CONSTRAINT:   "#ef4444",
    ALTERNATIVE_TO:   "#fb923c",
    COMPATIBLE_WITH:  "#34d399",
    MENTIONS_TOOL:    "#6ee7b7",
    SUPERSEDES:       "#818cf8",
    SIMILAR_TO:       "#94a3b8",
    CHANGED_TO:       "#fbbf24",
};

export const NODE_TYPES = ["全部", "Document", "Section", "Image", "Tool", "Material", "Process", "Constraint", "Table"] as const;
export const EDGE_TYPES = [
    "全部关系", "HAS_SECTION", "REFERENCES", "HAS_SUBSECTION", "HAS_IMAGE",
    "HAS_TABLE", "REQUIRES_TOOL", "USES_MATERIAL", "INVOLVES_PROCESS", "HAS_CONSTRAINT",
    "ALTERNATIVE_TO", "COMPATIBLE_WITH", "SUPERSEDES", "SIMILAR_TO",
] as const;

export type NodeFilter  = typeof NODE_TYPES[number];
export type EdgeFilter  = typeof EDGE_TYPES[number];
export type RenderMode  = "svg" | "canvas" | "webgl" | "heatmap";

export function nodeRadius(d: SimNode, heatNorm = 0): number {
    const t = d.type || d.label;
    if (t === "Document")   return 36;
    if (t === "Image")      return 18;
    if (t === "Constraint") return 14;
    if (t === "Tool" || t === "Material" || t === "Process") return 16;
    if (t === "Table")      return Math.round(12 + Math.min((d.row_count ?? 2), 20) * 0.8);
    return Math.round(22 + heatNorm * 16);
}
