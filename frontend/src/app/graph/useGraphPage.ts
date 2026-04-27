"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import * as d3 from "d3";
import { fetchApi } from "@/lib/api";
import type { GraphNode, GraphData, NodeFilter, EdgeFilter, RenderMode, Limits } from "./constants";
import type { GraphStats } from "./constants";
import { drawGraph } from "./renderSVG";
import { drawGraphCanvas } from "./renderCanvas";
import { drawGraphHeatmap } from "./renderHeatmap";
import { drawGraphWebGL } from "./renderWebGL";
import { useTour } from "./useTour";
import { useGraphTheme, getGraphThemeColors } from "./useGraphTheme";
import { findMatchingNodes, type GraphDocumentOption } from "./graphUtils";

interface GraphPageRefs {
  svgRef: RefObject<SVGSVGElement | null>;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  webglRef: RefObject<HTMLCanvasElement | null>;
  tooltipRef: RefObject<HTMLDivElement | null>;
}

export function useGraphPage({ svgRef, canvasRef, webglRef, tooltipRef }: GraphPageRefs) {
  const zoomRef = useRef<any>(null);
  const pixiDestroyRef = useRef<(() => void) | null>(null);
  const filteredNodesRef = useRef<GraphNode[]>([]);
  const filteredEdgesRef = useRef<any[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const resizeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [renderMode, setRenderMode] = useState<RenderMode>("canvas");
  const [manualMode, setManualMode] = useState<RenderMode | null>("canvas");
  const [redrawKey, setRedrawKey] = useState(0);
  const [data, setData] = useState<GraphData | null>(null);
  const [heatMap, setHeatMap] = useState<Map<string, number>>(new Map());
  const [scale, setScale] = useState(1);
  const [nodeFilter, setNodeFilter] = useState<NodeFilter>("全部");
  const [edgeFilter, setEdgeFilter] = useState<EdgeFilter>("全部关系");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());
  const [docFilter, setDocFilter] = useState("");
  const [docs, setDocs] = useState<{ doc_id: string; title: string }[]>([]);
  const [docSearchResults, setDocSearchResults] = useState<GraphDocumentOption[]>([]);
  const [nodeSearchResults, setNodeSearchResults] = useState<GraphNode[]>([]);
  const [pendingFocusId, setPendingFocusId] = useState<string | null>(null);
  const [limits, setLimits] = useState<Limits>({ doc: 100, sec: 500, entity: 200, tbl: 0, show_level: 0, show_images: true, show_entities: true });
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null);
  const [expandingId, setExpandingId] = useState<string | null>(null);
  const [showLimits, setShowLimits] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [copied, setCopied] = useState(false);
  const isDarkTheme = useGraphTheme();
  const graphTheme = getGraphThemeColors(isDarkTheme);

  function activeEl() {
    if (renderMode === "webgl") return webglRef.current as Element | null;
    if (renderMode === "svg") return svgRef.current as Element | null;
    return canvasRef.current as Element | null;
  }
  function zoomIn() {
    const el = activeEl();
    if (el && zoomRef.current) (d3.select(el) as any).transition().call(zoomRef.current.scaleBy, 1.3);
  }
  function zoomOut() {
    const el = activeEl();
    if (el && zoomRef.current) (d3.select(el) as any).transition().call(zoomRef.current.scaleBy, 0.7);
  }
  function zoomReset() {
    const el = activeEl();
    if (el && zoomRef.current) (d3.select(el) as any).transition().call(zoomRef.current.transform, d3.zoomIdentity);
  }

  const focusNode = useCallback((node: GraphNode, delay = 0, targetScale = 1.6) => {
    window.setTimeout(() => {
      const el = activeEl();
      if (!el || !zoomRef.current) return;
      const simNode = filteredNodesRef.current.find((n) => n.id === node.id) as (GraphNode & { x?: number; y?: number }) | undefined;
      if (simNode?.x === undefined || simNode?.y === undefined) return;
      const w = (el as HTMLElement).clientWidth;
      const h = (el as HTMLElement).clientHeight;
      (d3.select(el) as any).transition().duration(700).call(
        zoomRef.current.transform,
        d3.zoomIdentity.translate(w / 2 - simNode.x * targetScale, h / 2 - simNode.y * targetScale).scale(targetScale),
      );
    }, delay);
  }, [renderMode]); // eslint-disable-line react-hooks/exhaustive-deps

  function zoomToNode(nodeId: string, delay = 900) {
    setTimeout(() => {
      const simNode = filteredNodesRef.current.find((n) => n.id === nodeId) as any;
      if (!simNode?.x || !simNode?.y || !zoomRef.current) return;
      const el = activeEl();
      if (!el) return;
      const w = (el as HTMLElement).clientWidth;
      const h = (el as HTMLElement).clientHeight;
      (d3.select(el) as any).transition().duration(700).call(
        zoomRef.current.transform,
        d3.zoomIdentity.translate(w / 2 - simNode.x * 1.6, h / 2 - simNode.y * 1.6).scale(1.6),
      );
    }, delay);
  }

  const tour = useTour(zoomToNode, setNodeFilter);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.has("nf")) setNodeFilter(p.get("nf") as NodeFilter);
    if (p.has("ef")) setEdgeFilter(p.get("ef") as EdgeFilter);
    if (p.has("df")) setDocFilter(p.get("df")!);
    if (p.has("ld") || p.has("ls") || p.has("le") || p.has("lt"))
      setLimits((prev) => ({ ...prev, doc: Number(p.get("ld") || 100), sec: Number(p.get("ls") || 500), entity: Number(p.get("le") || 200), tbl: Number(p.get("lt") || 0) }));
    if (p.has("sq")) setSearchQuery(p.get("sq")!);
    if (p.has("sn") && data) {
      const node = data.nodes.find((n) => n.id === p.get("sn")!);
      if (node) setSelectedNode(node);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const p = new URLSearchParams();
    if (nodeFilter !== "全部") p.set("nf", nodeFilter);
    if (edgeFilter !== "全部关系") p.set("ef", edgeFilter);
    if (searchQuery) p.set("sq", searchQuery);
    if (docFilter) p.set("df", docFilter);
    if (limits.doc !== 100) p.set("ld", String(limits.doc));
    if (limits.sec !== 500) p.set("ls", String(limits.sec));
    if (limits.entity !== 200) p.set("le", String(limits.entity));
    if (limits.tbl !== 0) p.set("lt", String(limits.tbl));
    if (selectedNode) p.set("sn", selectedNode.id);
    const qs = p.toString();
    window.history.replaceState(null, "", qs ? `${window.location.pathname}?${qs}` : window.location.pathname);
  }, [nodeFilter, edgeFilter, searchQuery, docFilter, limits, selectedNode]);

  const refreshNodeSearch = useCallback((query: string, graphData: GraphData | null) => {
    if (!query.trim() || !graphData) {
      setNodeSearchResults([]);
      setHighlightedIds(new Set());
      return [];
    }
    const matches = findMatchingNodes(query, graphData.nodes);
    setNodeSearchResults(matches.slice(0, 8));
    setHighlightedIds(new Set(matches.map((node) => node.id)));
    return matches;
  }, []);

  useEffect(() => {
    const params = new URLSearchParams({
      limit_doc: String(limits.doc), limit_sec: String(limits.sec),
      limit_entity: String(limits.entity), limit_tbl: String(limits.tbl),
      doc_id: docFilter, hide_logos: "true",
      show_level: String(limits.show_level),
      show_images: String(limits.show_images), show_entities: String(limits.show_entities),
    });
    fetchApi<GraphData>(`/api/graph?${params}`)
      .then((d: GraphData) => { setData(d); if (d.stats) setGraphStats(d.stats); })
      .catch(() => {});
  }, [limits, docFilter]);

  async function expandSection(chunkId: string) {
    setExpandingId(chunkId);
    try {
      const { nodes: children } = await fetchApi<{ nodes: GraphNode[] }>(`/api/graph/expand/${chunkId}`);
      if (!children?.length) return;
      setData((prev) => {
        if (!prev) return prev;
        const existingIds = new Set(prev.nodes.map((n) => n.id));
        const newNodes = (children as GraphNode[]).filter((n) => !existingIds.has(n.id));
        const newEdges = children.map((c: GraphNode) => ({ source: chunkId, target: c.id, type: "HAS_SUBSECTION" }));
        return { ...prev, nodes: [...prev.nodes, ...newNodes], edges: [...prev.edges, ...newEdges] };
      });
    } finally {
      setExpandingId(null);
    }
  }

  useEffect(() => {
    fetchApi<{ data?: Array<{ doc_id: string; title?: string }> }>("/api/documents?per_page=500")
      .then((d) => setDocs((d.data || []).map((doc: any) => ({ doc_id: doc.doc_id, title: doc.title || "" }))))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchApi<{ nodes?: Array<{ chunk_id: string; heat_norm: number }> }>("/api/graph/hot-nodes?days=30&top_k=200")
      .then((d: any) => {
        if (d?.nodes?.length) setHeatMap(new Map(d.nodes.map((n: any) => [n.chunk_id, n.heat_norm])));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current);
      resizeTimerRef.current = setTimeout(() => setRedrawKey((k) => k + 1), 150);
    });
    ro.observe(el);
    return () => { ro.disconnect(); if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current); };
  }, []);

  const handleSearch = useCallback((q: string) => {
    setSearchQuery(q);
    const matches = refreshNodeSearch(q, data);
    if (matches.length > 0) focusNode(matches[0], 0, 1.35);
  }, [data, focusNode, refreshNodeSearch]);

  const handleSelectNodeResult = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    setSearchQuery(node.name || node.id);
    refreshNodeSearch(node.name || node.id, data);
    focusNode(node);
  }, [data, focusNode, refreshNodeSearch]);

  const handleSelectDocumentResult = useCallback((doc: GraphDocumentOption) => {
    setDocFilter(doc.doc_id);
    setNodeFilter("全部");
    setSelectedNode(null);
    setSearchQuery(doc.doc_id);
    setPendingFocusId(doc.doc_id);
  }, []);

  useEffect(() => { refreshNodeSearch(searchQuery, data); }, [data, searchQuery, refreshNodeSearch]);

  useEffect(() => {
    const query = searchQuery.trim();
    if (!query) { setDocSearchResults([]); return; }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetchApi<{ data?: Array<{ doc_id?: string; title?: string }> }>(
        `/api/documents?page=1&per_page=8&q=${encodeURIComponent(query)}`,
        { signal: controller.signal },
      )
        .then((payload) => {
          const matches = (payload.data || []).map((doc) => ({ doc_id: doc.doc_id || "", title: doc.title || "" })).filter((doc) => doc.doc_id);
          setDocSearchResults(matches);
        })
        .catch(() => { if (!controller.signal.aborted) setDocSearchResults([]); });
    }, 180);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [searchQuery]);

  useEffect(() => {
    if (!pendingFocusId || !data) return;
    const target = data.nodes.find((node) => node.id === pendingFocusId);
    if (!target) return;
    setSelectedNode(target);
    refreshNodeSearch(pendingFocusId, data);
    focusNode(target, 120);
    setPendingFocusId(null);
  }, [data, focusNode, pendingFocusId, refreshNodeSearch]);

  function exportGraph(format: "json" | "graphml") {
    const nodes = filteredNodesRef.current, edges = filteredEdgesRef.current;
    if (!nodes.length) return;
    if (format === "json") {
      const blob = new Blob([JSON.stringify({ nodes, edges }, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "graph.json";
      a.click();
    } else {
      const lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<graphml xmlns="http://graphml.graphdrawing.org/graphml">', '<graph id="G" edgedefault="directed">'];
      nodes.forEach((n) => lines.push(`  <node id="${n.id}"><data key="name">${(n.name || "").replace(/&/g, "&amp;")}</data><data key="type">${n.type || ""}</data></node>`));
      edges.forEach((e, i) => {
        const src = typeof e.source === "object" ? e.source.id : e.source;
        const tgt = typeof e.target === "object" ? e.target.id : e.target;
        lines.push(`  <edge id="e${i}" source="${src}" target="${tgt}"><data key="type">${e.type}</data></edge>`);
      });
      lines.push("</graph>", "</graphml>");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "application/xml" }));
      a.download = "graph.graphml";
      a.click();
    }
  }

  function shareSnapshot() {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const effectiveData = tour.tourOpen && tour.tourData ? tour.tourData : data;
  useEffect(() => {
    if (!effectiveData || !tooltipRef.current) return;
    const filteredNodes = effectiveData.nodes
      .filter((n) => !tour.tourOpen || nodeFilter === "全部" || (n.type || n.label) === nodeFilter)
      .map((n) => ({ ...n, x: undefined, y: undefined }));
    const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = effectiveData.edges
      .filter((e) =>
        (edgeFilter === "全部关系" || e.type === edgeFilter) &&
        filteredNodeIds.has(typeof e.source === "string" ? e.source : (e.source as any).id) &&
        filteredNodeIds.has(typeof e.target === "string" ? e.target : (e.target as any).id),
      )
      .map((e) => ({ ...e }));
    filteredNodesRef.current = filteredNodes;
    filteredEdgesRef.current = filteredEdges;
    if (pixiDestroyRef.current) { pixiDestroyRef.current(); pixiDestroyRef.current = null; }
    const nc = filteredNodes.length;
    const autoMode: RenderMode = nc > 5000 ? "heatmap" : nc > 1000 ? "webgl" : nc > 500 ? "canvas" : "svg";
    const mode = manualMode ?? autoMode;
    setRenderMode(mode);
    let canceled = false;
    if (mode === "heatmap" && canvasRef.current) {
      zoomRef.current = drawGraphHeatmap({ nodes: filteredNodes, edges: filteredEdges }, canvasRef.current, heatMap, (docId) => { window.location.href = `/library/${docId}`; });
    } else if (mode === "webgl" && webglRef.current && tooltipRef.current) {
      const wRef = webglRef.current, tRef = tooltipRef.current;
      import("pixi.js")
        .then((PIXI) => {
          if (canceled) return;
          drawGraphWebGL(PIXI, { nodes: filteredNodes, edges: filteredEdges }, wRef, tRef, setScale, (node) => setSelectedNode(node), highlightedIds, heatMap, isDarkTheme)
            .then(({ zoom, destroy }) => {
              pixiDestroyRef.current = destroy;
              if (canceled) { destroy(); pixiDestroyRef.current = null; return; }
              zoomRef.current = zoom;
            })
            .catch(() => {});
        })
        .catch(() => {});
    } else if (mode === "canvas" && canvasRef.current) {
      zoomRef.current = drawGraphCanvas(
        { nodes: filteredNodes, edges: filteredEdges }, canvasRef.current, tooltipRef.current!,
        setScale, (node) => setSelectedNode(node), highlightedIds, heatMap,
        tour.tourOpen ? tour.tourNodeIds : undefined, tour.tourOpen ? tour.tourCurrentId : undefined, isDarkTheme,
      );
    } else if (svgRef.current) {
      zoomRef.current = drawGraph(
        { nodes: filteredNodes, edges: filteredEdges }, svgRef.current, tooltipRef.current!,
        setScale, (node) => setSelectedNode(node), highlightedIds, heatMap,
        tour.tourOpen ? tour.tourNodeIds : undefined, tour.tourOpen ? tour.tourCurrentId : undefined, isDarkTheme,
      );
    }
    return () => {
      canceled = true;
      if (pixiDestroyRef.current) { pixiDestroyRef.current(); pixiDestroyRef.current = null; }
    };
  }, [effectiveData, nodeFilter, edgeFilter, highlightedIds, heatMap, manualMode, tour.tourNodeIds, tour.tourCurrentId, tour.tourOpen, redrawKey, isDarkTheme]); // eslint-disable-line react-hooks/exhaustive-deps

  function onExpandAll(docFilterArg: string, showImages: boolean, showEntities: boolean, totalNodes: number) {
    if (totalNodes > 500 && !confirm(`当前文档共有约 ${totalNodes} 个节点，全部展开可能影响性能，确认？`)) return;
    const params = new URLSearchParams({ limit_doc: "9999", limit_sec: "9999", limit_entity: "9999", limit_tbl: "0", doc_id: docFilterArg, show_level: "0", show_images: String(showImages), show_entities: String(showEntities), expand_all: "true" });
    fetchApi<GraphData>(`/api/graph?${params}`)
      .then((d: GraphData) => { setData(d); if (d.stats) setGraphStats(d.stats); })
      .catch(() => {});
  }

  return {
    containerRef, filteredNodesRef, zoomRef,
    renderMode, manualMode, setManualMode, scale,
    graphStats, heatMap,
    nodeFilter, setNodeFilter, edgeFilter, setEdgeFilter,
    selectedNode, setSelectedNode, searchQuery,
    docFilter, setDocFilter, docs,
    docSearchResults, nodeSearchResults,
    limits, setLimits, expandingId,
    showLimits, setShowLimits, showLegend, setShowLegend,
    showExport, setShowExport, copied,
    isDarkTheme, graphTheme, tour,
    zoomIn, zoomOut, zoomReset, focusNode,
    handleSearch, handleSelectNodeResult, handleSelectDocumentResult,
    expandSection, exportGraph, shareSnapshot, onExpandAll,
  };
}
