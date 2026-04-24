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
    HAS_ANNOTATION:   "#f87171",
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
    "HAS_TABLE", "REQUIRES_TOOL", "USES_MATERIAL", "INVOLVES_PROCESS", "HAS_CONSTRAINT", "HAS_ANNOTATION",
    "ALTERNATIVE_TO", "COMPATIBLE_WITH", "SUPERSEDES", "SIMILAR_TO",
] as const;

export type NodeFilter  = typeof NODE_TYPES[number];
export type EdgeFilter  = typeof EDGE_TYPES[number];
export type RenderMode  = "svg" | "canvas" | "webgl" | "heatmap";
export type NodeShape = "circle" | "roundedRect" | "pill" | "square" | "diamond" | "hexagon";

export function nodeRadius(d: SimNode, heatNorm = 0): number {
    const t = d.type || d.label;
    if (t === "Document")   return 36;
    if (t === "Image")      return 18;
    if (t === "Constraint") return 14;
    if (t === "Tool" || t === "Material" || t === "Process") return 16;
    if (t === "Table")      return Math.round(12 + Math.min((d.row_count ?? 2), 20) * 0.8);
    return Math.round(22 + heatNorm * 16);
}

export function nodeShape(d: Pick<GraphNode, "type" | "label">): NodeShape {
    const t = d.type || d.label;
    if (t === "Document") return "roundedRect";
    if (t === "Section") return "pill";
    if (t === "Image") return "square";
    if (t === "Constraint") return "diamond";
    if (t === "Process") return "hexagon";
    return "circle";
}

export function nodeDimensions(d: SimNode, heatNorm = 0, expand = 0): { r: number; width: number; height: number } {
    const r = nodeRadius(d, heatNorm) + expand;
    const shape = nodeShape(d);
    if (shape === "roundedRect") return { r, width: r * 2.5, height: r * 1.55 };
    if (shape === "pill") return { r, width: Math.max(76, r * 3.15), height: r * 1.45 };
    if (shape === "square") return { r, width: r * 2.1, height: r * 2.1 };
    if (shape === "diamond") return { r, width: r * 2.3, height: r * 2.3 };
    if (shape === "hexagon") return { r, width: r * 2.55, height: r * 1.95 };
    return { r, width: r * 2, height: r * 2 };
}

export function nodeCornerRadius(d: SimNode, heatNorm = 0, expand = 0): number {
    const { height } = nodeDimensions(d, heatNorm, expand);
    const shape = nodeShape(d);
    if (shape === "pill") return height / 2;
    if (shape === "roundedRect") return Math.min(height * 0.32, 18 + expand);
    return 0;
}

export function nodePolygonVertices(d: SimNode, heatNorm = 0, expand = 0): Array<[number, number]> {
    const { width, height } = nodeDimensions(d, heatNorm, expand);
    const hw = width / 2;
    const hh = height / 2;
    const shape = nodeShape(d);

    if (shape === "diamond") {
        return [
            [0, -hh],
            [hw, 0],
            [0, hh],
            [-hw, 0],
        ];
    }
    if (shape === "hexagon") {
        return [
            [-hw * 0.92, 0],
            [-hw * 0.46, -hh],
            [hw * 0.46, -hh],
            [hw * 0.92, 0],
            [hw * 0.46, hh],
            [-hw * 0.46, hh],
        ];
    }
    return [];
}

export function nodePolygonPoints(d: SimNode, heatNorm = 0, expand = 0): string {
    return nodePolygonVertices(d, heatNorm, expand)
        .map(([x, y]) => `${x},${y}`)
        .join(" ");
}

function pointInPolygon(x: number, y: number, vertices: Array<[number, number]>): boolean {
    let inside = false;
    for (let i = 0, j = vertices.length - 1; i < vertices.length; j = i++) {
        const [xi, yi] = vertices[i];
        const [xj, yj] = vertices[j];
        const intersects = ((yi > y) !== (yj > y))
            && (x < (xj - xi) * (y - yi) / ((yj - yi) || Number.EPSILON) + xi);
        if (intersects) inside = !inside;
    }
    return inside;
}

export function nodeContainsPoint(d: SimNode, x: number, y: number, heatNorm = 0): boolean {
    const shape = nodeShape(d);
    const { r, width, height } = nodeDimensions(d, heatNorm);
    const hw = width / 2;
    const hh = height / 2;

    if (shape === "circle") {
        return x * x + y * y <= r * r;
    }
    if (shape === "square") {
        return Math.abs(x) <= hw && Math.abs(y) <= hh;
    }
    if (shape === "diamond") {
        return (Math.abs(x) / hw) + (Math.abs(y) / hh) <= 1;
    }
    if (shape === "hexagon") {
        return pointInPolygon(x, y, nodePolygonVertices(d, heatNorm));
    }
    if (shape === "pill") {
        const innerHalf = Math.max(0, hw - hh);
        if (Math.abs(x) <= innerHalf && Math.abs(y) <= hh) return true;
        const cx = x < 0 ? -innerHalf : innerHalf;
        return (x - cx) ** 2 + y ** 2 <= hh ** 2;
    }
    return Math.abs(x) <= hw && Math.abs(y) <= hh;
}
