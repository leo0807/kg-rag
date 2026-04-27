import type { GraphNode } from "./constants";

export interface GraphDocumentOption {
  doc_id: string;
  title: string;
}

export function normalizeSearchText(value: string | undefined): string {
  return (value || "").trim().toLowerCase();
}

export function rankTextMatch(query: string, ...values: Array<string | undefined>): number {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) return Number.POSITIVE_INFINITY;
  let bestScore = Number.POSITIVE_INFINITY;
  for (const value of values) {
    const normalizedValue = normalizeSearchText(value);
    if (!normalizedValue) continue;
    if (normalizedValue === normalizedQuery) return 0;
    if (normalizedValue.startsWith(normalizedQuery)) bestScore = Math.min(bestScore, 1);
    const containsIdx = normalizedValue.indexOf(normalizedQuery);
    if (containsIdx >= 0) bestScore = Math.min(bestScore, 10 + containsIdx);
  }
  return bestScore;
}

export function findMatchingNodes(query: string, nodes: GraphNode[]): GraphNode[] {
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) return [];
  return nodes
    .map((node) => ({
      node,
      score: rankTextMatch(
        normalizedQuery,
        node.name, node.id, node.doc_id, node.number,
        `${node.doc_id || ""} ${node.name || ""}`,
      ),
    }))
    .filter((item) => Number.isFinite(item.score))
    .sort((a, b) => a.score - b.score || a.node.name.localeCompare(b.node.name))
    .map((item) => item.node);
}
