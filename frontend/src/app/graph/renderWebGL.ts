import * as d3 from "d3";
import { GraphData, GraphNode, SimNode, NODE_COLOR, MIN_SCALE, MAX_SCALE, nodeRadius } from "./constants";

export async function drawGraphWebGL(
    PIXI: typeof import("pixi.js"),
    data: GraphData,
    canvasEl: HTMLCanvasElement,
    tooltipEl: HTMLDivElement,
    onScaleChange: (s: number) => void,
    onNodeClick: (node: GraphNode) => void,
    highlightedIds: Set<string>,
    heatMap: Map<string, number>,
    isDarkTheme = true,
): Promise<{ zoom: d3.ZoomBehavior<HTMLCanvasElement, unknown>; destroy: () => void }> {
    const width  = canvasEl.clientWidth;
    const height = canvasEl.clientHeight;

    const app = new PIXI.Application({
        view:            canvasEl,
        width, height,
        backgroundColor: isDarkTheme ? 0x030712 : 0xf8fafc,
        antialias:       true,
        resolution:      window.devicePixelRatio || 1,
        autoDensity:     true,
    });

    const edgeGfx   = new PIXI.Graphics();
    const nodeLayer = new PIXI.Container();
    if (app.stage) {
        app.stage.addChild(edgeGfx);
        app.stage.addChild(nodeLayer);
    }

    const nodes = data.nodes as SimNode[];
    nodes.forEach(n => {
        if (n.x === undefined) { n.x = width  / 2 + (Math.random() - 0.5) * 200; }
        if (n.y === undefined) { n.y = height / 2 + (Math.random() - 0.5) * 200; }
    });

    const nc = nodes.length;
    const texCache = new Map<string, any>();
    function getTex(color: string, r: number): any {
        const key = `${color}|${r}`;
        if (!texCache.has(key)) {
            const g = new PIXI.Graphics();
            g.beginFill(parseInt(color.replace("#", ""), 16));
            g.drawCircle(r + 1, r + 1, r);
            g.endFill();
            texCache.set(key, app.renderer.generateTexture(g));
        }
        return texCache.get(key)!;
    }

    const sprites = new Map<string, any>();
    const labels  = new Map<string, any>();
    const containers = new Map<string, any>();

    nodes.forEach(n => {
        const type  = n.type || n.label;
        const color = NODE_COLOR[type] ?? "#6b7280";
        const heat  = heatMap.get(n.id) ?? 0;
        const r     = nodeRadius(n, heat);
        
        const container = new PIXI.Container();
        container.x = n.x!;
        container.y = n.y!;
        
        const sp = new PIXI.Sprite(getTex(color, r));
        sp.anchor.set(0.5);
        sp.alpha     = highlightedIds.size === 0 || highlightedIds.has(n.id) ? 1 : 0.25;
        sp.eventMode = "static";
        sp.cursor    = "pointer";
        sp.on("pointerdown", () => onNodeClick(n));
        container.addChild(sp);
        
        // Add Label
        const txt = new PIXI.Text(n.name || n.label || n.id, {
            fontSize:   12,
            fill:       isDarkTheme ? 0xffffff : 0x0f172a,
            align:      "center",
            fontWeight: "normal",
        });
        txt.anchor.set(0.5, 0);
        txt.y = r + 4;
        txt.visible = false; // Hidden by default, shown on zoom
        container.addChild(txt);

        nodeLayer.addChild(container);
        sprites.set(n.id, sp);
        labels.set(n.id, txt);
        containers.set(n.id, container);
    });

    const simulation = d3.forceSimulation(nodes)
        .force("link",    d3.forceLink(data.edges).id((d: any) => d.id).distance(nc > 500 ? 45 : 90))
        .force("charge",  d3.forceManyBody().strength(nc > 500 ? -60 : -200))
        .force("center",  d3.forceCenter(width / 2, height / 2))
        .force("collide", d3.forceCollide<SimNode>().radius(d => nodeRadius(d) + 3))
        .alphaDecay(0.04).velocityDecay(0.45);

    let tick = 0;
    simulation.on("tick", () => {
        tick++;
        nodes.forEach(n => { 
            const c = containers.get(n.id); 
            if (c) { c.x = n.x!; c.y = n.y!; } 
        });
        if (tick % 2 === 0) {
            edgeGfx.clear();
            edgeGfx.lineStyle(0.6, 0x4b5563, 0.5);
            data.edges.forEach(e => {
                const s = e.source as SimNode, t = e.target as SimNode;
                if (s.x != null && t.x != null) { edgeGfx.moveTo(s.x, s.y!); edgeGfx.lineTo(t.x, t.y!); }
            });
        }
    });

    const zoom = d3.zoom<HTMLCanvasElement, unknown>()
        .scaleExtent([MIN_SCALE, MAX_SCALE])
        .on("zoom", event => {
            const t = event.transform;
            if (app.stage) {
                app.stage.x = t.x; app.stage.y = t.y;
                app.stage.scale.set(t.k);
            }
            onScaleChange(t.k);
            
            // Toggle label visibility based on zoom
            const showLabels = t.k > 0.8;
            labels.forEach(l => { l.visible = showLabels; });
        });
    d3.select(canvasEl).call(zoom);
    d3.select(canvasEl).call(zoom.transform, d3.zoomIdentity);

    d3.select(canvasEl).on("mousemove.wtooltip", (event: MouseEvent) => {
        const tr = d3.zoomTransform(canvasEl);
        const mx = (event.offsetX - tr.x) / tr.k;
        const my = (event.offsetY - tr.y) / tr.k;
        let found: SimNode | null = null;
        for (const n of nodes) {
            const r = nodeRadius(n, heatMap.get(n.id) ?? 0);
            const dx = (n.x ?? 0) - mx, dy = (n.y ?? 0) - my;
            if (dx * dx + dy * dy <= r * r) { found = n; break; }
        }
        if (found) {
            tooltipEl.classList.remove("hidden");
            tooltipEl.style.left = (event.clientX + 12) + "px";
            tooltipEl.style.top  = (event.clientY - 8)  + "px";
            const nodeType = (found as any).type as string | undefined;
            if (nodeType === "Image") {
                const badge = (found as any).is_drawing
                    ? `<span style="background:#6366f1;color:${isDarkTheme ? "#ffffff" : "#0f172a"};font-size:10px;padding:1px 5px;border-radius:4px;margin-left:4px;">图纸</span>`
                    : "";
                const caption = found.name || found.id;
                const hint = `<div style="color:${isDarkTheme ? "#6b7280" : "#64748b"};font-size:10px;margin-top:4px;">点击节点查看图片</div>`;
                tooltipEl.innerHTML =
                    `<div style="font-weight:500;">${caption}${badge}</div>${hint}`;
            } else {
                const desc = (found as any).description || (found as any).content;
                tooltipEl.innerHTML = desc
                    ? `<div class="font-medium">${found.name}</div><div class="text-gray-400 mt-1 max-w-xs">${String(desc).slice(0, 80)}…</div>`
                    : found.name;
            }
        } else {
            tooltipEl.classList.add("hidden");
        }
    });
    d3.select(canvasEl).on("mouseleave.wtooltip", () => tooltipEl.classList.add("hidden"));

    function destroy() {
        simulation.stop();
        d3.select(canvasEl).on("mousemove.wtooltip", null).on("mouseleave.wtooltip", null);
        d3.select(canvasEl).on("click.heatmap", null);
        try { app.destroy(false, { children: true, texture: true, baseTexture: true }); } catch { /* ignore */ }
    }
    return { zoom, destroy };
}
