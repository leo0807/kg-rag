import * as d3 from "d3";
import { GraphData, MIN_SCALE, MAX_SCALE } from "./constants";

export function drawGraphHeatmap(
    data: GraphData,
    canvasEl: HTMLCanvasElement,
    heatMap: Map<string, number>,
    onDocClick: (docId: string) => void,
): d3.ZoomBehavior<HTMLCanvasElement, unknown> {
    const dpr    = window.devicePixelRatio || 1;
    const width  = canvasEl.clientWidth;
    const height = canvasEl.clientHeight;
    canvasEl.width  = width  * dpr;
    canvasEl.height = height * dpr;
    const ctx = canvasEl.getContext("2d")!;
    ctx.scale(dpr, dpr);

    interface ClusterItem {
        docId: string; name: string;
        count: number; maxHeat: number;
        cx: number; cy: number; r: number;
    }
    const clusterMap = new Map<string, { count: number; maxHeat: number; name: string }>();
    data.nodes.forEach(n => {
        if ((n.type || n.label) !== "Section") return;
        const docId = n.doc_id || "unknown";
        const heat  = heatMap.get(n.id) ?? 0;
        if (!clusterMap.has(docId)) clusterMap.set(docId, { count: 0, maxHeat: 0, name: docId });
        const c = clusterMap.get(docId)!;
        c.count++;
        c.maxHeat = Math.max(c.maxHeat, heat);
    });
    data.nodes.forEach(n => {
        if ((n.type || n.label) !== "Document") return;
        const docId = n.doc_id || n.id;
        if (clusterMap.has(docId)) clusterMap.get(docId)!.name = n.name || docId;
    });

    const items = [...clusterMap.entries()];
    const cols  = Math.max(1, Math.ceil(Math.sqrt(items.length)));
    const rows  = Math.ceil(items.length / cols);
    const cellW = width  / cols;
    const cellH = height / rows;

    const positioned: ClusterItem[] = items.map(([docId, info], i) => ({
        docId,
        name:    info.name,
        count:   info.count,
        maxHeat: info.maxHeat,
        cx: cellW * (i % cols + 0.5),
        cy: cellH * (Math.floor(i / cols) + 0.5),
        r:  Math.max(20, Math.min(Math.sqrt(info.count) * 9, Math.min(cellW, cellH) * 0.38)),
    }));

    let transform = d3.zoomIdentity;

    function draw() {
        ctx.clearRect(0, 0, width, height);
        ctx.save();
        ctx.translate(transform.x, transform.y);
        ctx.scale(transform.k, transform.k);
        positioned.forEach(item => {
            const heat = item.maxHeat;
            if (heat > 0.1) {
                ctx.beginPath();
                ctx.arc(item.cx, item.cy, item.r + 7, 0, Math.PI * 2);
                ctx.strokeStyle = `rgba(245,158,11,${0.25 + heat * 0.5})`;
                ctx.lineWidth   = 1.5 + heat * 3;
                ctx.stroke();
            }
            ctx.beginPath();
            ctx.arc(item.cx, item.cy, item.r, 0, Math.PI * 2);
            ctx.fillStyle   = heat > 0.1 ? `rgba(245,158,11,${0.25 + heat * 0.45})` : "rgba(99,102,241,0.35)";
            ctx.strokeStyle = heat > 0.1 ? "#f59e0b" : "#6366f1";
            ctx.lineWidth   = 1.5;
            ctx.fill(); ctx.stroke();
            const fs = Math.max(10, Math.min(14, item.r * 0.38));
            ctx.fillStyle = "rgba(255,255,255,0.9)";
            ctx.font = `bold ${fs}px sans-serif`;
            ctx.textAlign = "center"; ctx.textBaseline = "middle";
            ctx.fillText(String(item.count), item.cx, item.cy);
            const lfs   = Math.max(9, Math.min(11, item.r * 0.22));
            const label = item.name.length > 14 ? item.name.slice(0, 14) + "…" : item.name;
            ctx.font      = `${lfs}px sans-serif`;
            ctx.fillStyle = "rgba(255,255,255,0.55)";
            ctx.fillText(label, item.cx, item.cy + item.r + 13);
        });
        ctx.restore();
    }

    draw();
    const zoom = d3.zoom<HTMLCanvasElement, unknown>()
        .scaleExtent([MIN_SCALE, MAX_SCALE])
        .on("zoom", event => { transform = event.transform; draw(); });
    d3.select(canvasEl).call(zoom);
    d3.select(canvasEl).call(zoom.transform, d3.zoomIdentity);
    d3.select(canvasEl).on("click.heatmap", (event: MouseEvent) => {
        const inv = transform.invert([event.offsetX, event.offsetY]);
        const mx = inv[0], my = inv[1];
        for (const item of positioned) {
            const dx = mx - item.cx, dy = my - item.cy;
            if (dx * dx + dy * dy <= item.r * item.r) { onDocClick(item.docId); return; }
        }
    });
    return zoom;
}
