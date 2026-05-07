import type { GraphData, GraphEdge, GraphNode, GraphStats } from "./constants";

export type GraphZoomBucket = "overview" | "mid" | "detail";

function nodeType(node: GraphNode): string {
  return node.type || node.label || "";
}

function edgeKey(edge: GraphEdge): string {
  const source = typeof edge.source === "string" ? edge.source : edge.source.id;
  const target = typeof edge.target === "string" ? edge.target : edge.target.id;
  return `${source}__${target}__${edge.type}__${edge.predicted ? "1" : "0"}`;
}

export function getGraphZoomBucket(scale: number): GraphZoomBucket {
  if (scale < 0.3) return "overview";
  if (scale < 0.8) return "mid";
  return "detail";
}

export function summarizeGraphData(data: GraphData): GraphStats {
  let docs = 0;
  let sections = 0;
  let images = 0;
  let tables = 0;
  let entities = 0;

  for (const node of data.nodes) {
    const type = nodeType(node);
    if (type === "Document") docs += 1;
    else if (type === "Section") sections += 1;
    else if (type === "Image") images += 1;
    else if (type === "Table") tables += 1;
    else entities += 1;
  }

  return {
    total: data.nodes.length,
    docs,
    sections,
    images,
    tables,
    entities,
  };
}

export function mergeGraphData(
  base: GraphData | null,
  incoming: GraphData,
): GraphData {
  if (!base) {
    return {
      nodes: [...incoming.nodes],
      edges: [...incoming.edges],
      stats: incoming.stats || summarizeGraphData(incoming),
    };
  }

  const nodeMap = new Map<string, GraphNode>();
  for (const node of base.nodes) nodeMap.set(node.id, node);
  for (const node of incoming.nodes) nodeMap.set(node.id, node);

  const edgeMap = new Map<string, GraphEdge>();
  for (const edge of base.edges) edgeMap.set(edgeKey(edge), edge);
  for (const edge of incoming.edges) edgeMap.set(edgeKey(edge), edge);

  const merged = {
    nodes: Array.from(nodeMap.values()),
    edges: Array.from(edgeMap.values()),
    stats: summarizeGraphData({
      nodes: Array.from(nodeMap.values()),
      edges: Array.from(edgeMap.values()),
    }),
  };

  return merged;
}

export function filterGraphByZoom(
  data: GraphData | null,
  scale: number,
): GraphData | null {
  if (!data) return null;
  const bucket = getGraphZoomBucket(scale);
  if (bucket === "detail") return data;

  const nodes = data.nodes.filter((node) => {
    const type = nodeType(node);
    if (type === "Document") return true;
    if (bucket === "mid") return type === "Section" && (node.level ?? 1) <= 1;
    return false;
  });

  const keepIds = new Set(nodes.map((node) => node.id));
  const edges = data.edges.filter((edge) => {
    const source =
      typeof edge.source === "string" ? edge.source : edge.source.id;
    const target =
      typeof edge.target === "string" ? edge.target : edge.target.id;
    if (!keepIds.has(source) || !keepIds.has(target)) return false;
    if (bucket === "overview") return edge.type === "REFERENCES";
    return true;
  });

  return {
    nodes,
    edges,
    stats: summarizeGraphData({ nodes, edges }),
  };
}
