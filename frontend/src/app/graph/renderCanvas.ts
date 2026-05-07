import * as d3 from "d3";
import {
  EDGE_COLOR,
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

function drawNodePath(
  ctx: CanvasRenderingContext2D,
  node: SimNode,
  heatNorm = 0,
  expand = 0,
) {
  const shape = nodeShape(node);
  const { r, width, height } = nodeDimensions(node, heatNorm, expand);
  const hw = width / 2;
  const hh = height / 2;

  ctx.beginPath();
  if (shape === "roundedRect" || shape === "pill" || shape === "square") {
    const radius = nodeCornerRadius(node, heatNorm, expand);
    ctx.roundRect(-hw, -hh, width, height, radius);
    return;
  }
  if (shape === "diamond" || shape === "hexagon") {
    const vertices = nodePolygonVertices(node, heatNorm, expand);
    vertices.forEach(([x, y], index) => {
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();
    return;
  }
  ctx.arc(0, 0, r, 0, 2 * Math.PI);
}

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
  isDarkTheme = true,
  colorOverride?: Map<string, string>,
  userAnnotatedIds?: Set<string>,
): d3.ZoomBehavior<HTMLCanvasElement, unknown> {
  const labelFill = isDarkTheme ? "#ffffff" : "#0f172a";
  const tooltipHint = isDarkTheme ? "#6b7280" : "#64748b";
  const tourMode = (tourNodeIds?.size ?? 0) > 0;
  const dpr = window.devicePixelRatio || 1;
  const width = canvasEl.clientWidth;
  const height = canvasEl.clientHeight;
  canvasEl.width = width * dpr;
  canvasEl.height = height * dpr;
  const canvasCtx = canvasEl.getContext("2d");
  if (canvasCtx === null) {
    throw new Error("2d canvas context unavailable");
  }
  const ctx: CanvasRenderingContext2D = canvasCtx;
  ctx.scale(dpr, dpr);

  const nodes = data.nodes as SimNode[];
  const margin = 160;
  nodes.forEach((n) => {
    if (n.x === undefined) {
      n.x = width / 2 + (Math.random() - 0.5) * 200;
      n.y = height / 2 + (Math.random() - 0.5) * 200;
    }
  });

  const nc = nodes.length;
  const simulation = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink<SimNode, GraphEdge>(data.edges as GraphEdge[])
        .id((d) => d.id)
        .distance(nc > 50 ? 60 : 140),
    )
    .force(
      "charge",
      d3.forceManyBody().strength(nc > 200 ? -60 : nc > 50 ? -120 : -500),
    )
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force(
      "collide",
      d3
        .forceCollide<SimNode>()
        .radius((d) => nodeRadius(d) + 6)
        .strength(0.7),
    )
    .alphaDecay(nc > 200 ? 0.06 : 0.03)
    .velocityDecay(0.4)
    .alphaMin(0.05);

  let transform = d3.zoomIdentity;

  function isVisibleNode(n: SimNode): boolean {
    if (n.x == null || n.y == null) return false;
    const sx = n.x * transform.k + transform.x;
    const sy = n.y * transform.k + transform.y;
    return (
      sx > -margin &&
      sx < width + margin &&
      sy > -margin &&
      sy < height + margin
    );
  }

  function getNodeAt(mx: number, my: number): SimNode | null {
    const [sx, sy] = transform.invert([mx, my]);
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i];
      const nx = n.x;
      const ny = n.y;
      if (nx == null || ny == null) continue;
      if (nodeContainsPoint(n, sx - nx, sy - ny, heatMap.get(n.id) ?? 0))
        return n;
    }
    return null;
  }

  function render() {
    ctx.save();
    ctx.clearRect(0, 0, width, height);
    ctx.translate(transform.x, transform.y);
    ctx.scale(transform.k, transform.k);

    const visibleNodes = nodes.filter(isVisibleNode);
    const visibleIds = new Set(visibleNodes.map((n) => n.id));

    for (const e of data.edges) {
      const s = e.source as SimNode;
      const t = e.target as SimNode;
      const sx = s.x;
      const sy = s.y;
      const tx = t.x;
      const ty = t.y;
      if (sx == null || sy == null || tx == null || ty == null) continue;
      if (!visibleIds.has(s.id) && !visibleIds.has(t.id)) continue;
      const opacity = tourMode
        ? (tourNodeIds?.has(s.id) ?? false) && (tourNodeIds?.has(t.id) ?? false)
          ? 0.85
          : 0.05
        : 0.6;
      ctx.globalAlpha = e.predicted ? 0.4 : opacity;
      ctx.strokeStyle = EDGE_COLOR[e.type] ?? "#374151";
      ctx.lineWidth = e.type === "REFERENCES" ? 2 : 1.5;
      ctx.setLineDash(
        e.predicted
          ? [6, 4]
          : e.type === "HAS_IMAGE" ||
              e.type === "MENTIONS_TOOL" ||
              e.type === "HAS_ANNOTATION"
            ? [4, 2]
            : [],
      );
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(tx, ty);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    for (const n of visibleNodes) {
      const heatNorm = heatMap.get(n.id) ?? 0;
      const color =
        colorOverride?.get(n.id) ?? NODE_COLOR[n.type || n.label] ?? "#6b7280";
      const isCurrent = n.id === tourCurrentId;
      const inPath = tourNodeIds?.has(n.id) ?? false;
      const opacity = tourMode ? (isCurrent ? 1 : inPath ? 0.72 : 0.1) : 0.95;
      const isHighlight = highlightedIds.has(n.id);
      const isRefTarget = !!(n as GraphNode).is_reference_target;
      const isHot =
        !tourMode && heatNorm > 0.15 && (n.type || n.label) === "Section";
      const nx = n.x;
      const ny = n.y;
      if (nx == null || ny == null) continue;

      if (isHot) {
        ctx.save();
        ctx.translate(nx, ny);
        ctx.globalAlpha = 0.25 + heatNorm * 0.45;
        ctx.strokeStyle = "#f59e0b";
        ctx.lineWidth = 1.5 + heatNorm * 3;
        drawNodePath(ctx, n, heatNorm, 7 + heatNorm * 4);
        ctx.stroke();
        ctx.restore();
      }
      if (tourMode && isCurrent) {
        ctx.save();
        ctx.translate(nx, ny);
        ctx.globalAlpha = 0.75;
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = 3.5;
        drawNodePath(ctx, n, heatNorm, 11);
        ctx.stroke();
        ctx.restore();
      }
      if (!tourMode && isHighlight) {
        ctx.save();
        ctx.translate(nx, ny);
        ctx.globalAlpha = 0.9;
        ctx.strokeStyle = "#f97316";
        ctx.lineWidth = 2.5;
        drawNodePath(ctx, n, heatNorm, 6);
        ctx.stroke();
        ctx.restore();
      }
      ctx.save();
      ctx.translate(nx, ny);
      ctx.globalAlpha = isRefTarget ? opacity * 0.45 : opacity;
      ctx.fillStyle = color;
      drawNodePath(ctx, n, heatNorm);
      ctx.fill();
      if (isRefTarget) {
        ctx.globalAlpha = 0.65;
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        drawNodePath(ctx, n, heatNorm, 2);
        ctx.stroke();
        ctx.setLineDash([]);
      } else if (userAnnotatedIds?.has(n.id)) {
        ctx.globalAlpha = 0.85;
        ctx.strokeStyle = "#a78bfa";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 2]);
        drawNodePath(ctx, n, heatNorm, 3);
        ctx.stroke();
        ctx.setLineDash([]);
      } else if (isCurrent || isHighlight) {
        ctx.strokeStyle = isCurrent ? "#fbbf24" : "#f97316";
        ctx.lineWidth = 2.5;
        ctx.stroke();
      }
      ctx.restore();
      const nodeType = n.type || n.label;
      let labelText: string | null = null;
      if (nodeType === "Document") {
        const raw = n.doc_id || n.name || "";
        labelText = raw.length > 7 ? `${raw.slice(0, 7)}…` : raw;
      } else if (nodeType === "Section" && (n.level ?? 1) === 1) {
        labelText = n.number || "";
      }
      if (labelText) {
        ctx.globalAlpha = tourMode && !inPath && !isCurrent ? 0.3 : 1;
        ctx.fillStyle = labelFill;
        ctx.font = `${nodeType === "Document" ? 12 : 10}px Arial`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(labelText, nx, ny);
      }
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  let rafPending = false;
  simulation.on("tick", () => {
    if (rafPending) return;
    rafPending = true;
    requestAnimationFrame(() => {
      rafPending = false;
      render();
    });
  });

  const zoom = d3
    .zoom<HTMLCanvasElement, unknown>()
    .scaleExtent([MIN_SCALE, MAX_SCALE])
    .filter((event) => event.type !== "dblclick") // dblclick handled separately for node navigation
    .on("zoom", (event) => {
      transform = event.transform;
      onScaleChange(event.transform.k);
      render();
    });

  const sel = d3.select(canvasEl);
  sel.call(zoom);
  sel.call(zoom.transform, d3.zoomIdentity);
  sel
    .style("cursor", "grab")
    .on("mousedown.cursor", () => sel.style("cursor", "grabbing"))
    .on("mouseup.cursor", () => sel.style("cursor", "grab"));

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
      tooltipEl.classList.remove("hidden");
      tooltipEl.style.left = `${event.clientX + 12}px`;
      tooltipEl.style.top = `${event.clientY - 8}px`;
      const richNode = n as GraphNode;
      const nodeType = richNode.type;
      if (nodeType === "Image") {
        const badge = richNode.is_drawing
          ? `<span style="background:#6366f1;color:${labelFill};font-size:10px;padding:1px 5px;border-radius:4px;margin-left:4px;">图纸</span>`
          : "";
        const caption = n.name || n.id;
        const hint = `<div style="color:${tooltipHint};font-size:10px;margin-top:4px;">点击节点查看图片</div>`;
        tooltipEl.innerHTML = `<div style="font-weight:500;">${caption}${badge}</div>${hint}`;
      } else {
        const desc = richNode.description || richNode.content;
        tooltipEl.innerHTML = desc
          ? `<div class="font-medium">${n.name}</div><div class="text-gray-400 mt-1 max-w-xs">${String(desc).slice(0, 80)}…</div>`
          : n.name;
      }
    } else {
      tooltipEl.classList.add("hidden");
    }
  });

  sel.on("mouseleave.nodes", () => tooltipEl.classList.add("hidden"));

  sel.on("dblclick.nodes", (event: MouseEvent) => {
    event.preventDefault();
    const rect = canvasEl.getBoundingClientRect();
    const n = getNodeAt(event.clientX - rect.left, event.clientY - rect.top);
    if (!n) return;
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
  });

  return zoom;
}
