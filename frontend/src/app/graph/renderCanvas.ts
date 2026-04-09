import * as d3 from "d3";
import { GraphData, GraphNode, SimNode, NODE_COLOR, EDGE_COLOR, MIN_SCALE, MAX_SCALE, nodeRadius } from "./constants";

export function drawGraphCanvas(
    data: GraphData,
    canvasEl: HTMLCanvasElement,
    tooltipEl: HTMLDivElement,
    onScaleChange: (s: number) => void,
    onNodeClick: (node: GraphNode) => void,
    highlightedIds: Set<string>,
    heatMap: Map<string, number>,
    tourNodeIds?: Set<string>,
    tourCurrentId?: string,
): d3.ZoomBehavior<HTMLCanvasElement, unknown> {
    const tourMode = (tourNodeIds?.size ?? 0) > 0;
    const dpr    = window.devicePixelRatio || 1;
    const width  = canvasEl.clientWidth;
    const height = canvasEl.clientHeight;
    canvasEl.width  = width  * dpr;
    canvasEl.height = height * dpr;
    const ctx = canvasEl.getContext("2d")!;
    ctx.scale(dpr, dpr);

    const nodes = data.nodes as SimNode[];
    nodes.forEach(n => {
        if (n.x === undefined) {
            n.x = width  / 2 + (Math.random() - 0.5) * 200;
            n.y = height / 2 + (Math.random() - 0.5) * 200;
        }
    });

    const nc = nodes.length;
    const simulation = d3.forceSimulation(nodes)
        .force("link",    d3.forceLink(data.edges).id((d: any) => d.id).distance(nc > 50 ? 60 : 140))
        .force("charge",  d3.forceManyBody().strength(nc > 50 ? -120 : -500))
        .force("center",  d3.forceCenter(width / 2, height / 2))
        .force("collide", d3.forceCollide<SimNode>().radius(d => nodeRadius(d) + 6).strength(0.7))
        .alphaDecay(0.03).velocityDecay(0.4);

    let transform = d3.zoomIdentity;

    function getNodeAt(mx: number, my: number): SimNode | null {
        const [sx, sy] = transform.invert([mx, my]);
        for (let i = nodes.length - 1; i >= 0; i--) {
            const n = nodes[i];
            if (n.x == null) continue;
            const r = nodeRadius(n);
            if ((sx - n.x!) ** 2 + (sy - n.y!) ** 2 <= r * r) return n;
        }
        return null;
    }

    function render() {
        ctx.save();
        ctx.clearRect(0, 0, width, height);
        ctx.translate(transform.x, transform.y);
        ctx.scale(transform.k, transform.k);

        for (const e of data.edges) {
            const s = e.source as SimNode;
            const t = e.target as SimNode;
            if (s.x == null || t.x == null) continue;
            const opacity = tourMode
                ? ((tourNodeIds!.has(s.id) && tourNodeIds!.has(t.id)) ? 0.85 : 0.05)
                : 0.6;
            ctx.globalAlpha  = opacity;
            ctx.strokeStyle  = EDGE_COLOR[e.type] ?? "#374151";
            ctx.lineWidth    = e.type === "REFERENCES" ? 2 : 1.5;
            ctx.setLineDash(e.type === "HAS_IMAGE" || e.type === "MENTIONS_TOOL" ? [4, 2] : []);
            ctx.beginPath();
            ctx.moveTo(s.x!, s.y!);
            ctx.lineTo(t.x!, t.y!);
            ctx.stroke();
        }
        ctx.setLineDash([]);

        for (const n of nodes) {
            if (n.x == null) continue;
            const heatNorm  = heatMap.get(n.id) ?? 0;
            const r         = nodeRadius(n, heatNorm);
            const color     = NODE_COLOR[n.type || n.label] ?? "#6b7280";
            const isCurrent = n.id === tourCurrentId;
            const inPath    = tourNodeIds?.has(n.id) ?? false;
            const opacity   = tourMode ? (isCurrent ? 1 : inPath ? 0.72 : 0.1) : 0.95;
            const isHighlight = highlightedIds.has(n.id);
            const isHot     = !tourMode && heatNorm > 0.15 && (n.type || n.label) === "Section";

            if (isHot) {
                ctx.globalAlpha = 0.25 + heatNorm * 0.45;
                ctx.strokeStyle = "#f59e0b";
                ctx.lineWidth   = 1.5 + heatNorm * 3;
                ctx.beginPath();
                ctx.arc(n.x!, n.y!, r + 7, 0, 2 * Math.PI);
                ctx.stroke();
            }
            if (tourMode && isCurrent) {
                ctx.globalAlpha = 0.75;
                ctx.strokeStyle = "#fbbf24";
                ctx.lineWidth   = 3.5;
                ctx.beginPath();
                ctx.arc(n.x!, n.y!, r + 11, 0, 2 * Math.PI);
                ctx.stroke();
            }
            if (!tourMode && isHighlight) {
                ctx.globalAlpha = 0.9;
                ctx.strokeStyle = "#f97316";
                ctx.lineWidth   = 2.5;
                ctx.beginPath();
                ctx.arc(n.x!, n.y!, r + 6, 0, 2 * Math.PI);
                ctx.stroke();
            }
            ctx.globalAlpha = opacity;
            ctx.fillStyle   = color;
            ctx.beginPath();
            ctx.arc(n.x!, n.y!, r, 0, 2 * Math.PI);
            ctx.fill();
            if (isCurrent || isHighlight) {
                ctx.strokeStyle = isCurrent ? "#fbbf24" : "#f97316";
                ctx.lineWidth   = 2.5;
                ctx.stroke();
            }
            ctx.globalAlpha    = (tourMode && !inPath && !isCurrent) ? 0.3 : 1;
            ctx.fillStyle      = "#fff";
            ctx.font           = `${(n.type || n.label) === "Document" ? 12 : 10}px Arial`;
            ctx.textAlign      = "center";
            ctx.textBaseline   = "middle";
            const nm = n.name || n.label || "";
            ctx.fillText(nm.length > 6 ? nm.slice(0, 6) + "…" : nm, n.x!, n.y!);
        }
        ctx.globalAlpha = 1;
        ctx.restore();
    }

    simulation.on("tick", render);

    const zoom = d3.zoom<HTMLCanvasElement, unknown>()
        .scaleExtent([MIN_SCALE, MAX_SCALE])
        .on("zoom", event => { transform = event.transform; onScaleChange(event.transform.k); render(); });

    const sel = d3.select(canvasEl);
    sel.call(zoom);
    sel.call(zoom.transform, d3.zoomIdentity);
    sel.style("cursor", "grab")
        .on("mousedown.cursor", () => sel.style("cursor", "grabbing"))
        .on("mouseup.cursor",   () => sel.style("cursor", "grab"));

    sel.on("click.nodes", (event: MouseEvent) => {
        if (event.defaultPrevented) return;
        const rect = canvasEl.getBoundingClientRect();
        const n = getNodeAt(event.clientX - rect.left, event.clientY - rect.top);
        if (n) onNodeClick(n as GraphNode);
    });

    sel.on("mousemove.nodes", (event: MouseEvent) => {
        const rect = canvasEl.getBoundingClientRect();
        const n = getNodeAt(event.clientX - rect.left, event.clientY - rect.top);
        if (n) {
            const desc = (n as any).description || (n as any).content;
            tooltipEl.classList.remove("hidden");
            tooltipEl.style.left = (event.clientX + 12) + "px";
            tooltipEl.style.top  = (event.clientY - 8)  + "px";
            tooltipEl.innerHTML  = desc
                ? `<div class="font-medium">${n.name}</div><div class="text-gray-400 mt-1 max-w-xs">${String(desc).slice(0, 80)}…</div>`
                : n.name;
        } else {
            tooltipEl.classList.add("hidden");
        }
    });

    sel.on("mouseleave.nodes", () => tooltipEl.classList.add("hidden"));
    return zoom;
}
