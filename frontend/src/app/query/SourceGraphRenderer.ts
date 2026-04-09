import * as d3 from "d3";

// ── 颜色配置（与主图谱页保持一致）─────────────────────────────────────────
export const NODE_COLOR: Record<string, string> = {
    Document:   "#6366f1",
    Section:    "#f59e0b",
    Tool:       "#10b981",
    Material:   "#f97316",
    Process:    "#a78bfa",
    Constraint: "#ef4444",
};

export const EDGE_COLOR: Record<string, string> = {
    HAS_SECTION:       "#4f46e5",
    HAS_SUBSECTION:    "#d97706",
    NEXT_SECTION:      "#4b5563",
    REQUIRES_TOOL:     "#10b981",
    USES_MATERIAL:     "#f97316",
    INVOLVES_PROCESS:  "#a78bfa",
    HAS_CONSTRAINT:    "#ef4444",
};

// 来源节点：排名 1~5 对应颜色，第 6 及之后统一用暗色
export const RANK_COLORS = [
    "#fbbf24", // rank 1 — 金
    "#34d399", // rank 2 — 绿
    "#60a5fa", // rank 3 — 蓝
    "#f472b6", // rank 4 — 粉
    "#a78bfa", // rank 5 — 紫
];

export function rankColor(rank: number) {
    return RANK_COLORS[rank - 1] ?? "#6b7280";
}

export interface GraphNode {
    id: string; name: string; type: string;
    doc_id?: string; rank: number;
    x?: number; y?: number; fx?: number | null; fy?: number | null;
}
export interface GraphEdge { source: string; target: string; type: string; }

export function drawSourceGraph(
    svgEl: SVGSVGElement,
    data: { nodes: GraphNode[]; edges: GraphEdge[] },
) {
    const W = svgEl.clientWidth;
    const H = svgEl.clientHeight;
    d3.select(svgEl).selectAll("*").remove();

    const svg       = d3.select(svgEl);
    const container = svg.append("g");

    // 允许平移/缩放
    const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 4])
        .on("zoom", e => container.attr("transform", e.transform));
    svg.call(zoom).style("cursor", "grab")
        .on("mousedown.c", () => svg.style("cursor", "grabbing"))
        .on("mouseup.c",   () => svg.style("cursor", "grab"));

    const r = (d: GraphNode) => {
        if (d.type === "Document")   return 20;
        if (d.rank > 0)              return 18;
        if (d.type === "Constraint") return 10;
        return 12;
    };

    (data.nodes as GraphNode[]).forEach(n => {
        if (!n.x) { n.x = W / 2 + (Math.random() - 0.5) * 80; }
        if (!n.y) { n.y = H / 2 + (Math.random() - 0.5) * 80; }
    });

    const sim = d3.forceSimulation(data.nodes as GraphNode[])
        .force("link",    d3.forceLink(data.edges).id((d: any) => d.id).distance(80))
        .force("charge",  d3.forceManyBody().strength(-200))
        .force("center",  d3.forceCenter(W / 2, H / 2))
        .force("collide", d3.forceCollide<GraphNode>().radius(d => r(d) + 6).strength(0.9))
        .alphaDecay(0.03)
        .velocityDecay(0.45);

    // 边
    const link = container.append("g")
        .selectAll("line").data(data.edges).join("line")
        .attr("stroke",         (d: any) => EDGE_COLOR[d.type] ?? "#374151")
        .attr("stroke-width",   1.5)
        .attr("stroke-opacity", 0.5)
        .attr("stroke-dasharray", (d: any) =>
            d.type === "NEXT_SECTION" || d.type === "HAS_CONSTRAINT" ? "4 2" : null
        );

    // 边标签（关系类型，仅主要关系）
    const SHOW_LABEL = new Set(["REQUIRES_TOOL", "USES_MATERIAL", "INVOLVES_PROCESS", "HAS_CONSTRAINT"]);
    const linkLabel = container.append("g")
        .selectAll("text").data(data.edges.filter(e => SHOW_LABEL.has(e.type))).join("text")
        .attr("font-size", 8)
        .attr("fill", (d: any) => EDGE_COLOR[d.type] ?? "#9ca3af")
        .attr("text-anchor", "middle")
        .attr("pointer-events", "none")
        .attr("opacity", 0.75)
        .text((d: any) => d.type.replace(/_/g, " "));

    // 节点
    const node = container.append("g")
        .selectAll("g").data(data.nodes as GraphNode[]).join("g")
        .attr("cursor", "grab")
        .call(
            d3.drag<any, GraphNode>()
                .filter(e => e.button === 0)
                .on("start", (e, d) => {
                    e.sourceEvent.stopPropagation();
                    if (!e.active) sim.alphaTarget(0.3).restart();
                    d.fx = d.x; d.fy = d.y;
                })
                .on("drag",  (e, d) => { d.fx = e.x; d.fy = e.y; })
                .on("end",   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
        );

    // 来源节点加发光外圈
    node.filter((d: GraphNode) => d.rank > 0).append("circle")
        .attr("r", d => r(d) + 4)
        .attr("fill", "none")
        .attr("stroke", d => rankColor(d.rank))
        .attr("stroke-width", 1.5)
        .attr("stroke-opacity", 0.4);

    // 主体圆
    node.append("circle")
        .attr("r", d => r(d))
        .attr("fill", d => {
            if (d.rank > 0) return rankColor(d.rank);
            return NODE_COLOR[d.type] ?? "#6b7280";
        })
        .attr("fill-opacity", d => d.rank > 0 ? 1 : 0.7);

    // 文字
    node.append("text")
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "central")
        .attr("pointer-events", "none")
        .each(function (d: GraphNode) {
            const el = d3.select(this);
            if (d.rank > 0) {
                el.append("tspan")
                    .attr("x", 0).attr("dy", "-0.35em")
                    .attr("font-size", 11).attr("font-weight", "bold")
                    .attr("fill", "#000")
                    .text(`#${d.rank}`);
                el.append("tspan")
                    .attr("x", 0).attr("dy", "1.2em")
                    .attr("font-size", 8).attr("fill", "#1f2937")
                    .text(d.name.length > 6 ? d.name.slice(0, 6) + "…" : d.name);
            } else {
                el.append("tspan")
                    .attr("x", 0).attr("dy", "0em")
                    .attr("font-size", d.type === "Document" ? 9 : 8)
                    .attr("fill", "#fff")
                    .text(d.name.length > 5 ? d.name.slice(0, 5) + "…" : d.name);
            }
        });

    sim.on("tick", () => {
        link
            .attr("x1", (d: any) => d.source.x)
            .attr("y1", (d: any) => d.source.y)
            .attr("x2", (d: any) => d.target.x)
            .attr("y2", (d: any) => d.target.y);
        linkLabel
            .attr("x", (d: any) => (d.source.x + d.target.x) / 2)
            .attr("y", (d: any) => (d.source.y + d.target.y) / 2 - 4);
        node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });
}
