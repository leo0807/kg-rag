"use client";

import { useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import { toast } from "sonner";
import type { PipelineEdge, PipelineNode } from "./types";

type SetNodes = Dispatch<SetStateAction<PipelineNode[]>>;
type SetEdges = Dispatch<SetStateAction<PipelineEdge[]>>;

export function useClipboard(
  nodes: PipelineNode[],
  edges: PipelineEdge[],
  setNodes: SetNodes,
  setEdges: SetEdges,
  setSelectedNodeId: (id: string | null) => void,
  setValidateResult: (r: { valid: boolean; errors: string[] } | null) => void,
  nodeCounter: MutableRefObject<number>,
) {
  const [clipboard, setClipboard] = useState<{ nodes: PipelineNode[]; edges: PipelineEdge[] } | null>(null);

  function clearCanvas() {
    setNodes([]); setEdges([]); setSelectedNodeId(null); setValidateResult(null);
  }

  function copySelected() {
    const sel = nodes.filter((n) => n.selected);
    if (!sel.length) return;
    const ids = new Set(sel.map((n) => n.id));
    setClipboard({ nodes: sel, edges: edges.filter((e) => ids.has(e.source) && ids.has(e.target)) });
    toast.success(`已复制 ${sel.length} 个节点`);
  }

  function pasteClipboard() {
    if (!clipboard?.nodes.length) return;
    const idMap = new Map<string, string>();
    const newNodes = clipboard.nodes.map((n) => {
      const id = `${n.data.nodeType}_${++nodeCounter.current}`;
      idMap.set(n.id, id);
      return { ...n, id, position: { x: n.position.x + 40, y: n.position.y + 40 }, selected: true };
    });
    const newEdges = clipboard.edges.map((e) => ({
      ...e, id: `e_paste_${Date.now()}_${Math.random()}`,
      source: idMap.get(e.source) ?? e.source, target: idMap.get(e.target) ?? e.target,
    }));
    setNodes((ns) => [...ns.map((n) => ({ ...n, selected: false })), ...newNodes]);
    setEdges((es) => [...es, ...newEdges]);
  }

  function cutSelected() {
    const sel = nodes.filter((n) => n.selected);
    if (!sel.length) return;
    const ids = new Set(sel.map((n) => n.id));
    setClipboard({ nodes: sel, edges: edges.filter((e) => ids.has(e.source) && ids.has(e.target)) });
    setNodes((ns) => ns.filter((n) => !n.selected));
    setEdges((es) => es.filter((e) => !ids.has(e.source) && !ids.has(e.target)));
    toast.success(`已剪切 ${sel.length} 个节点`);
  }

  return { clearCanvas, copySelected, pasteClipboard, cutSelected, hasClipboard: !!clipboard };
}
