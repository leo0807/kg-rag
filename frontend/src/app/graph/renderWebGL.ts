import * as d3 from "d3";
import type {
  Container as PixiContainer,
  Sprite as PixiSprite,
  Text as PixiText,
  Texture as PixiTexture,
} from "pixi.js";
import {
  type GraphData,
  type GraphEdge,
  type GraphNode,
  MAX_SCALE,
  MIN_SCALE,
  NODE_COLOR,
  nodeContainsPoint,
  nodeCornerRadius,
  nodeDimensions,
  nodePolygonVertices,
  nodeRadius,
  nodeShape,
  type SimNode,
} from "./constants";

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
): Promise<{
  zoom: d3.ZoomBehavior<HTMLCanvasElement, unknown>;
  destroy: () => void;
}> {
  const width = canvasEl.clientWidth;
  const height = canvasEl.clientHeight;

  const app = new PIXI.Application({
    view: canvasEl,
    width,
    height,
    backgroundColor: isDarkTheme ? 0x030712 : 0xf8fafc,
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  });

  const edgeGfx = new PIXI.Graphics();
  const nodeLayer = new PIXI.Container();
  if (app.stage) {
    app.stage.addChild(edgeGfx);
    app.stage.addChild(nodeLayer);
  }

  const nodes = data.nodes as SimNode[];
  const margin = 160;
  nodes.forEach((n) => {
    if (n.x === undefined) {
      n.x = width / 2 + (Math.random() - 0.5) * 200;
    }
    if (n.y === undefined) {
      n.y = height / 2 + (Math.random() - 0.5) * 200;
    }
  });

  const nc = nodes.length;
  const texCache = new Map<string, PixiTexture>();
  function getTex(node: SimNode, color: string, heatNorm = 0): PixiTexture {
    const shape = nodeShape(node);
    const { r, width, height } = nodeDimensions(node, heatNorm);
    const key = `${shape}|${color}|${width}|${height}|${r}`;
    if (!texCache.has(key)) {
      const g = new PIXI.Graphics();
      g.beginFill(parseInt(color.replace("#", ""), 16));
      if (shape === "roundedRect" || shape === "pill" || shape === "square") {
        const radius = nodeCornerRadius(node, heatNorm);
        g.drawRoundedRect(1, 1, width, height, radius);
      } else if (shape === "diamond" || shape === "hexagon") {
        const points = nodePolygonVertices(node, heatNorm).flatMap(([x, y]) => [
          x + width / 2 + 1,
          y + height / 2 + 1,
        ]);
        g.drawPolygon(points);
      } else {
        g.drawCircle(r + 1, r + 1, r);
      }
      g.endFill();
      texCache.set(key, app.renderer.generateTexture(g));
    }
    const texture = texCache.get(key);
    if (texture) return texture;
    const fallback = app.renderer.generateTexture(new PIXI.Graphics());
    texCache.set(key, fallback);
    return fallback;
  }

  const sprites = new Map<string, PixiSprite>();
  const labels = new Map<string, PixiText>();
  const containers = new Map<string, PixiContainer>();
  let transform = d3.zoomIdentity;

  nodes.forEach((n) => {
    const nodeType = n.type || n.label;
    const color = NODE_COLOR[nodeType] ?? "#6b7280";
    const heat = heatMap.get(n.id) ?? 0;

    const container = new PIXI.Container();
    container.x = n.x ?? 0;
    container.y = n.y ?? 0;

    const sp = new PIXI.Sprite(getTex(n, color, heat));
    sp.anchor.set(0.5);
    sp.alpha = highlightedIds.size === 0 || highlightedIds.has(n.id) ? 1 : 0.25;
    sp.eventMode = "static";
    sp.cursor = "pointer";
    sp.on("pointerdown", () => onNodeClick(n));
    container.addChild(sp);

    // Labels: Document shows doc_id (12px), Section level=1 shows number (10px)
    let labelStr = "";
    if (nodeType === "Document") {
      const raw = n.doc_id || n.name || "";
      labelStr = raw.length > 7 ? `${raw.slice(0, 7)}…` : raw;
    } else if (nodeType === "Section" && (n.level ?? 1) === 1) {
      labelStr = n.number || "";
    }
    const txt = new PIXI.Text(labelStr, {
      fontSize: nodeType === "Document" ? 12 : 10,
      fill: isDarkTheme ? 0xffffff : 0x0f172a,
      align: "center",
      fontWeight: "normal",
    });
    txt.anchor.set(0.5, 0.5);
    txt.y = 0;
    txt.visible = false; // Shown when zoomed in and labelStr non-empty
    container.addChild(txt);

    nodeLayer.addChild(container);
    sprites.set(n.id, sp);
    labels.set(n.id, txt);
    containers.set(n.id, container);
  });

  const simulation = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink<SimNode, GraphEdge>(data.edges as GraphEdge[])
        .id((d) => d.id)
        .distance(nc > 500 ? 45 : 90),
    )
    .force("charge", d3.forceManyBody().strength(nc > 500 ? -60 : -200))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force(
      "collide",
      d3.forceCollide<SimNode>().radius((d) => nodeRadius(d) + 3),
    )
    .alphaDecay(0.04)
    .velocityDecay(0.45);

  let tick = 0;
  simulation.on("tick", () => {
    tick++;
    nodes.forEach((n) => {
      const c = containers.get(n.id);
      if (c) {
        c.x = n.x ?? 0;
        c.y = n.y ?? 0;
      }
    });
    if (tick % 2 === 0) updateVisibility();
  });

  function updateVisibility() {
    const visibleIds = new Set<string>();
    nodes.forEach((n) => {
      if (n.x == null || n.y == null) return;
      const sx = n.x * transform.k + transform.x;
      const sy = n.y * transform.k + transform.y;
      const visible =
        sx > -margin &&
        sx < width + margin &&
        sy > -margin &&
        sy < height + margin;
      const c = containers.get(n.id);
      if (c) c.visible = visible;
      if (visible) visibleIds.add(n.id);
    });
    edgeGfx.clear();
    edgeGfx.lineStyle(0.6, 0x4b5563, 0.5);
    data.edges.forEach((e) => {
      const s = e.source as SimNode,
        t = e.target as SimNode;
      if (s.x == null || t.x == null) return;
      if (!visibleIds.has(s.id) && !visibleIds.has(t.id)) return;
      edgeGfx.moveTo(s.x, s.y ?? 0);
      edgeGfx.lineTo(t.x, t.y ?? 0);
    });
  }

  const zoom = d3
    .zoom<HTMLCanvasElement, unknown>()
    .scaleExtent([MIN_SCALE, MAX_SCALE])
    .filter((event) => event.type !== "dblclick") // dblclick handled separately for node navigation
    .on("zoom", (event) => {
      const t = event.transform;
      transform = t;
      if (app.stage) {
        app.stage.x = t.x;
        app.stage.y = t.y;
        app.stage.scale.set(t.k);
      }
      onScaleChange(t.k);

      // Show labels only when zoomed in, and only for nodes that have label text
      const showLabels = t.k > 0.8;
      labels.forEach((l) => {
        l.visible = showLabels && l.text !== "";
      });
      updateVisibility();
    });
  d3.select(canvasEl).call(zoom);
  d3.select(canvasEl).call(zoom.transform, d3.zoomIdentity);
  updateVisibility();

  d3.select(canvasEl).on("mousemove.wtooltip", (event: MouseEvent) => {
    const tr = d3.zoomTransform(canvasEl);
    const mx = (event.offsetX - tr.x) / tr.k;
    const my = (event.offsetY - tr.y) / tr.k;
    let found: SimNode | null = null;
    for (const n of nodes) {
      const dx = mx - (n.x ?? 0);
      const dy = my - (n.y ?? 0);
      if (nodeContainsPoint(n, dx, dy, heatMap.get(n.id) ?? 0)) {
        found = n;
        break;
      }
    }
    if (found) {
      tooltipEl.classList.remove("hidden");
      tooltipEl.style.left = `${event.clientX + 12}px`;
      tooltipEl.style.top = `${event.clientY - 8}px`;
      const richNode = found as GraphNode & {
        is_drawing?: boolean;
        description?: string;
        content?: string;
      };
      const nodeType = richNode.type;
      if (nodeType === "Image") {
        const badge = richNode.is_drawing
          ? `<span style="background:#6366f1;color:${isDarkTheme ? "#ffffff" : "#0f172a"};font-size:10px;padding:1px 5px;border-radius:4px;margin-left:4px;">图纸</span>`
          : "";
        const caption = found.name || found.id;
        const hint = `<div style="color:${isDarkTheme ? "#6b7280" : "#64748b"};font-size:10px;margin-top:4px;">点击节点查看图片</div>`;
        tooltipEl.innerHTML = `<div style="font-weight:500;">${caption}${badge}</div>${hint}`;
      } else {
        const desc = richNode.description || richNode.content;
        tooltipEl.innerHTML = desc
          ? `<div class="font-medium">${found.name}</div><div class="text-gray-400 mt-1 max-w-xs">${String(desc).slice(0, 80)}…</div>`
          : found.name;
      }
    } else {
      tooltipEl.classList.add("hidden");
    }
  });
  d3.select(canvasEl).on("mouseleave.wtooltip", () =>
    tooltipEl.classList.add("hidden"),
  );

  d3.select(canvasEl).on("dblclick.nodes", (event: MouseEvent) => {
    event.preventDefault();
    const tr = d3.zoomTransform(canvasEl);
    const mx = (event.offsetX - tr.x) / tr.k;
    const my = (event.offsetY - tr.y) / tr.k;
    for (const n of nodes) {
      const dx = mx - (n.x ?? 0);
      const dy = my - (n.y ?? 0);
      if (!nodeContainsPoint(n, dx, dy, heatMap.get(n.id) ?? 0)) continue;
      const nodeType = (n.type || n.label) as string;
      const docId = (n as GraphNode).doc_id;
      if (nodeType === "Document") {
        window.open(`/library/${docId || n.id}`, "_blank");
      } else if (nodeType === "Section" && docId) {
        window.open(`/library/${docId}?section=${n.id}&preview=true`, "_blank");
      } else if (nodeType === "Image" && docId) {
        const pageNum = (n as GraphNode).page_num;
        window.open(
          `/library/${docId}?preview=true${pageNum != null ? `&page=${pageNum}` : ""}`,
          "_blank",
        );
      }
      break;
    }
  });

  function destroy() {
    simulation.stop();
    d3.select(canvasEl)
      .on("mousemove.wtooltip", null)
      .on("mouseleave.wtooltip", null);
    d3.select(canvasEl).on("click.heatmap", null);
    try {
      app.destroy(false, { children: true, texture: true, baseTexture: true });
    } catch {
      /* ignore */
    }
  }
  return { zoom, destroy };
}
