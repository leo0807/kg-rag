"use client";

import * as d3 from "d3";
import {
  type RefObject,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { fetchApi } from "@/lib/api";
import type {
  EdgeFilter,
  GraphData,
  GraphEdge,
  GraphNode,
  GraphStats,
  Limits,
  NodeFilter,
  RenderMode,
} from "./constants";
import { mergeGraphData, summarizeGraphData } from "./graphLazyUtils";
import { findMatchingNodes, type GraphDocumentOption } from "./graphUtils";
import { drawGraphCanvas } from "./renderCanvas";
import { drawGraph } from "./renderSVG";
import { drawGraphWebGL } from "./renderWebGL";
import { getGraphThemeColors, useGraphTheme } from "./useGraphTheme";
import { useTour } from "./useTour";

interface GraphPageRefs {
  svgRef: RefObject<SVGSVGElement | null>;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  webglRef: RefObject<HTMLCanvasElement | null>;
  tooltipRef: RefObject<HTMLDivElement | null>;
}

export function useGraphPage({
  svgRef,
  canvasRef,
  webglRef,
  tooltipRef,
}: GraphPageRefs) {
  const zoomRef = useRef<d3.ZoomBehavior<Element, unknown> | null>(null);
  const pixiDestroyRef = useRef<(() => void) | null>(null);
  const filteredNodesRef = useRef<GraphNode[]>([]);
  const filteredEdgesRef = useRef<GraphEdge[]>([]);
  const graphDataRef = useRef<GraphData | null>(null);
  const loadedDocIdsRef = useRef<Set<string>>(new Set());
  const loadedSectionIdsRef = useRef<Set<string>>(new Set());
  const searchRequestIdRef = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const resizeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [renderMode, setRenderMode] = useState<RenderMode>("canvas");
  const [manualMode, setManualMode] = useState<RenderMode | null>(null);
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
  const [docSearchResults, setDocSearchResults] = useState<
    GraphDocumentOption[]
  >([]);
  const [nodeSearchResults, setNodeSearchResults] = useState<GraphNode[]>([]);
  const [pendingFocusId, setPendingFocusId] = useState<string | null>(null);
  const [limits, setLimits] = useState<Limits>({
    doc: 100,
    sec: 500,
    entity: 200,
    tbl: 0,
    show_level: 0,
    show_images: true,
    show_entities: true,
  });
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null);
  const [expandingId, setExpandingId] = useState<string | null>(null);
  const [showLimits, setShowLimits] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [copied, setCopied] = useState(false);
  const [hideIsolated, setHideIsolated] = useState(true);
  const [viewStats, setViewStats] = useState({
    docCount: 0,
    noRefDocCount: 0,
    refEdgeCount: 0,
    hiddenIsolated: 0,
  });
  const [importanceMode, setImportanceMode] = useState(false);
  const [domainMode, setDomainMode] = useState(false);
  const [colorOverride, setColorOverride] = useState<Map<string, string>>(
    new Map(),
  );
  const [userAnnotatedIds, setUserAnnotatedIds] = useState<Set<string>>(
    new Set(),
  );
  const [showPredictions, setShowPredictions] = useState(false);
  const [predictionEdges, setPredictionEdges] = useState<GraphEdge[]>([]);
  const isDarkTheme = useGraphTheme();
  const graphTheme = getGraphThemeColors(isDarkTheme);

  const activeEl = useCallback(() => {
    if (renderMode === "webgl") return webglRef.current as Element | null;
    if (renderMode === "svg") return svgRef.current as Element | null;
    return canvasRef.current as Element | null;
  }, [canvasRef, renderMode, svgRef, webglRef]);

  const zoomSelection = useCallback((el: Element) => {
    return d3.select(el);
  }, []);
  function zoomIn() {
    const el = activeEl();
    if (el && zoomRef.current)
      zoomSelection(el).transition().call(zoomRef.current.scaleBy, 1.3);
  }
  function zoomOut() {
    const el = activeEl();
    if (el && zoomRef.current)
      zoomSelection(el).transition().call(zoomRef.current.scaleBy, 0.7);
  }
  function zoomReset() {
    const el = activeEl();
    if (el && zoomRef.current)
      zoomSelection(el)
        .transition()
        .call(zoomRef.current.transform, d3.zoomIdentity);
  }

  const focusNode = useCallback(
    (node: GraphNode, delay = 0, targetScale = 1.6) => {
      window.setTimeout(() => {
        const el = activeEl();
        if (!el || !zoomRef.current) return;
        const simNode = filteredNodesRef.current.find(
          (n) => n.id === node.id,
        ) as (GraphNode & { x?: number; y?: number }) | undefined;
        if (simNode?.x === undefined || simNode?.y === undefined) return;
        const w = (el as HTMLElement).clientWidth;
        const h = (el as HTMLElement).clientHeight;
        zoomSelection(el)
          .transition()
          .duration(700)
          .call(
            zoomRef.current.transform,
            d3.zoomIdentity
              .translate(
                w / 2 - simNode.x * targetScale,
                h / 2 - simNode.y * targetScale,
              )
              .scale(targetScale),
          );
      }, delay);
    },
    [activeEl, zoomSelection],
  ); // eslint-disable-line react-hooks/exhaustive-deps

  function zoomToNode(nodeId: string, delay = 900) {
    setTimeout(() => {
      const simNode = filteredNodesRef.current.find((n) => n.id === nodeId) as
        | (GraphNode & { x?: number; y?: number })
        | undefined;
      if (!simNode?.x || !simNode?.y || !zoomRef.current) return;
      const el = activeEl();
      if (!el) return;
      const w = (el as HTMLElement).clientWidth;
      const h = (el as HTMLElement).clientHeight;
      zoomSelection(el)
        .transition()
        .duration(700)
        .call(
          zoomRef.current.transform,
          d3.zoomIdentity
            .translate(w / 2 - simNode.x * 1.6, h / 2 - simNode.y * 1.6)
            .scale(1.6),
        );
    }, delay);
  }

  const tour = useTour(zoomToNode, setNodeFilter);
  const tourData = tour.tourOpen && tour.tourData ? tour.tourData : data;
  const effectiveData = useMemo(() => {
    if (!tourData) return null;
    return predictionEdges.length > 0
      ? { ...tourData, edges: [...tourData.edges, ...predictionEdges] }
      : tourData;
  }, [tourData, predictionEdges]);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.has("nf")) setNodeFilter(p.get("nf") as NodeFilter);
    if (p.has("ef")) setEdgeFilter(p.get("ef") as EdgeFilter);
    if (p.has("df")) setDocFilter(p.get("df") || "");
    if (p.has("ld") || p.has("ls") || p.has("le") || p.has("lt"))
      setLimits((prev) => ({
        ...prev,
        doc: Number(p.get("ld") || 100),
        sec: Number(p.get("ls") || 500),
        entity: Number(p.get("le") || 200),
        tbl: Number(p.get("lt") || 0),
      }));
    if (p.has("sq")) setSearchQuery(p.get("sq") || "");
    if (p.has("sn") && data) {
      const selectedId = p.get("sn") || "";
      const node = data.nodes.find((n) => n.id === selectedId);
      if (node) setSelectedNode(node);
    }
  }, [data]);

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
    window.history.replaceState(
      null,
      "",
      qs ? `${window.location.pathname}?${qs}` : window.location.pathname,
    );
  }, [nodeFilter, edgeFilter, searchQuery, docFilter, limits, selectedNode]);

  const refreshNodeSearch = useCallback(
    (query: string, graphData: GraphData | null) => {
      if (!query.trim() || !graphData) {
        setNodeSearchResults([]);
        setHighlightedIds(new Set());
        return [];
      }
      const matches = findMatchingNodes(query, graphData.nodes);
      setNodeSearchResults(matches.slice(0, 8));
      setHighlightedIds(new Set(matches.map((node) => node.id)));
      return matches;
    },
    [],
  );

  const replaceGraphData = useCallback((incoming: GraphData) => {
    graphDataRef.current = incoming;
    setData(incoming);
    setGraphStats(incoming.stats || summarizeGraphData(incoming));
  }, []);

  const mergeGraphIntoView = useCallback((incoming: GraphData) => {
    const merged = mergeGraphData(graphDataRef.current, incoming);
    graphDataRef.current = merged;
    setData(merged);
    setGraphStats(merged.stats || summarizeGraphData(merged));
  }, []);

  const loadOverviewGraph = useCallback(async () => {
    const params = new URLSearchParams({
      show_level: String(limits.show_level),
      show_images: String(limits.show_images),
      show_entities: String(limits.show_entities),
      limit_tbl: String(limits.tbl),
    });
    const payload = await fetchApi<GraphData>(`/api/graph?${params}`);
    loadedDocIdsRef.current.clear();
    loadedSectionIdsRef.current.clear();
    replaceGraphData(payload);
  }, [
    limits.show_entities,
    limits.show_images,
    limits.show_level,
    limits.tbl,
    replaceGraphData,
  ]);

  const loadDocumentGraph = useCallback(
    async (docId: string, replace = false) => {
      const normalized = docId.trim();
      if (!normalized) return;
      if (!replace && loadedDocIdsRef.current.has(normalized)) return;
      const payload = await fetchApi<GraphData>(
        `/api/graph/expand/doc/${encodeURIComponent(normalized)}`,
      );
      loadedDocIdsRef.current.add(normalized);
      for (const node of payload.nodes) {
        if ((node.type || node.label) === "Section" && node.id)
          loadedSectionIdsRef.current.add(node.id);
      }
      if (replace) {
        replaceGraphData(payload);
      } else {
        mergeGraphIntoView(payload);
      }
    },
    [mergeGraphIntoView, replaceGraphData],
  );

  const loadSectionGraph = useCallback(
    async (chunkId: string) => {
      const normalized = chunkId.trim();
      if (!normalized || loadedSectionIdsRef.current.has(normalized)) return;
      const payload = await fetchApi<GraphData>(
        `/api/graph/expand/section/${encodeURIComponent(normalized)}`,
      );
      loadedSectionIdsRef.current.add(normalized);
      mergeGraphIntoView(payload);
    },
    [mergeGraphIntoView],
  );

  const loadSearchGraph = useCallback(
    async (query: string) => {
      const trimmed = query.trim();
      if (!trimmed) return;
      const requestId = ++searchRequestIdRef.current;
      try {
        const payload = await fetchApi<GraphData>(
          `/api/graph/search?q=${encodeURIComponent(trimmed)}`,
        );
        if (requestId !== searchRequestIdRef.current) return;
        if (payload.nodes?.length) {
          mergeGraphIntoView(payload);
          const matches = payload.nodes.filter(
            (node) =>
              (node.type || node.label) === "Document" ||
              (node.type || node.label) === "Section",
          );
          setNodeSearchResults(matches.slice(0, 8));
          setHighlightedIds(new Set(matches.map((node) => node.id)));
          if (matches[0]) focusNode(matches[0], 0, 1.35);
        } else {
          refreshNodeSearch(trimmed, graphDataRef.current);
        }
      } catch {
        if (requestId === searchRequestIdRef.current) {
          refreshNodeSearch(trimmed, graphDataRef.current);
        }
      }
    },
    [focusNode, mergeGraphIntoView, refreshNodeSearch],
  );

  useEffect(() => {
    const load = async () => {
      try {
        if (docFilter) {
          await loadDocumentGraph(docFilter, true);
        } else {
          await loadOverviewGraph();
        }
      } catch {
        // ignore load failures; the UI keeps the previous graph visible
      }
    };
    load();
  }, [docFilter, loadDocumentGraph, loadOverviewGraph]);

  async function expandSection(chunkId: string) {
    setExpandingId(chunkId);
    try {
      await loadSectionGraph(chunkId);
    } finally {
      setExpandingId(null);
    }
  }

  useEffect(() => {
    fetchApi<{ data?: Array<{ doc_id: string; title?: string }> }>(
      "/api/documents?per_page=500",
    )
      .then((d) =>
        setDocs(
          (d.data || []).map((doc) => ({
            doc_id: doc.doc_id,
            title: doc.title || "",
          })),
        ),
      )
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchApi<{ nodes?: Array<{ chunk_id: string; heat_norm: number }> }>(
      "/api/graph/hot-nodes?days=30&top_k=200",
    )
      .then((d) => {
        if (d?.nodes?.length) {
          setHeatMap(new Map(d.nodes.map((n) => [n.chunk_id, n.heat_norm])));
        }
      })
      .catch(() => {});
  }, []);

  const getDomainColor = useCallback((docId: string): string => {
    const n = parseInt((docId ?? "").replace(/\D/g, "").slice(0, 4), 10) || 0;
    if (n < 1000) return "#3B82F6";
    if (n < 2000) return "#10B981";
    if (n < 3000) return "#F59E0B";
    if (n < 4000) return "#8B5CF6";
    if (n < 7000) return "#EF4444";
    return "#6B7280";
  }, []);

  const getImportanceColor = useCallback((imp: number): string => {
    if (imp > 0.7) return "#EF4444";
    if (imp > 0.3) return "#F5A623";
    return "#3B4F6B";
  }, []);

  useEffect(() => {
    if (!importanceMode) {
      if (!domainMode) setColorOverride(new Map());
      return;
    }
    fetchApi<{ nodes: { id: string; importance: number }[] }>(
      "/api/graph/importance",
    )
      .then((d) => {
        const m = new Map<string, string>();
        for (const n of d.nodes) m.set(n.id, getImportanceColor(n.importance));
        setColorOverride(m);
      })
      .catch(() => {});
  }, [domainMode, importanceMode, getImportanceColor]);

  useEffect(() => {
    if (!domainMode) {
      if (!importanceMode) setColorOverride(new Map());
      return;
    }
    if (!data) return;
    const m = new Map<string, string>();
    for (const node of data.nodes) {
      if ((node.type || node.label) === "Document" && node.doc_id)
        m.set(node.id, getDomainColor(node.doc_id));
    }
    setColorOverride(m);
  }, [data, domainMode, importanceMode, getDomainColor]);

  useEffect(() => {
    fetchApi<{ nodes: string[] }>("/api/knowledge/annotations")
      .then((r) => setUserAnnotatedIds(new Set(r.nodes)))
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!showPredictions) {
      setPredictionEdges([]);
      return;
    }
    fetchApi<{
      predictions: { source_id: string; target_id: string; score: number }[];
    }>("/api/graph/predictions")
      .then((d) =>
        setPredictionEdges(
          (d.predictions ?? []).map((p) => ({
            source: p.source_id,
            target: p.target_id,
            type: "PREDICTED",
            predicted: true,
            score: p.score,
          })),
        ),
      )
      .catch(() => {});
  }, [showPredictions]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current);
      resizeTimerRef.current = setTimeout(
        () => setRedrawKey((k) => k + 1),
        150,
      );
    });
    ro.observe(el);
    return () => {
      ro.disconnect();
      if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current);
    };
  }, []);

  const handleSearch = useCallback(
    (q: string) => {
      setSearchQuery(q);
      const matches = refreshNodeSearch(q, data);
      if (matches.length > 0) focusNode(matches[0], 0, 1.35);
    },
    [data, focusNode, refreshNodeSearch],
  );

  const handleSelectNodeResult = useCallback(
    (node: GraphNode) => {
      setSelectedNode(node);
      setSearchQuery(node.name || node.id);
      refreshNodeSearch(node.name || node.id, data);
      if ((node.type || node.label) === "Document") {
        setDocFilter(node.doc_id || node.id);
      }
      focusNode(node);
    },
    [data, focusNode, refreshNodeSearch],
  );

  const handleSelectDocumentResult = useCallback((doc: GraphDocumentOption) => {
    setDocFilter(doc.doc_id);
    setNodeFilter("全部");
    setSelectedNode(null);
    setSearchQuery(doc.doc_id);
    setPendingFocusId(doc.doc_id);
  }, []);

  useEffect(() => {
    refreshNodeSearch(searchQuery, data);
  }, [data, searchQuery, refreshNodeSearch]);

  useEffect(() => {
    const query = searchQuery.trim();
    if (!query) {
      setDocSearchResults([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetchApi<{ data?: Array<{ doc_id?: string; title?: string }> }>(
        `/api/documents?page=1&per_page=8&q=${encodeURIComponent(query)}`,
        { signal: controller.signal },
      )
        .then((payload) => {
          const matches = (payload.data || [])
            .map((doc) => ({
              doc_id: doc.doc_id || "",
              title: doc.title || "",
            }))
            .filter((doc) => doc.doc_id);
          setDocSearchResults(matches);
        })
        .catch(() => {
          if (!controller.signal.aborted) setDocSearchResults([]);
        });
    }, 180);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [searchQuery]);

  useEffect(() => {
    const query = searchQuery.trim();
    if (!query) return;
    const timer = window.setTimeout(() => {
      void loadSearchGraph(query);
    }, 220);
    return () => window.clearTimeout(timer);
  }, [loadSearchGraph, searchQuery]);

  useEffect(() => {
    if (!pendingFocusId || !data) return;
    const target = data.nodes.find((node) => node.id === pendingFocusId);
    if (!target) return;
    setSelectedNode(target);
    refreshNodeSearch(pendingFocusId, data);
    focusNode(target, 120);
    setPendingFocusId(null);
  }, [data, focusNode, pendingFocusId, refreshNodeSearch]);

  useEffect(() => {
    if (!selectedNode) return;
    const type = selectedNode.type || selectedNode.label;
    if (type !== "Document") return;
    const docId = selectedNode.doc_id || selectedNode.id;
    if (!docId || docFilter === docId) return;
    setDocFilter(docId);
  }, [docFilter, selectedNode]);

  function exportGraph(format: "json" | "graphml") {
    const nodes = filteredNodesRef.current,
      edges = filteredEdgesRef.current;
    if (!nodes.length) return;
    if (format === "json") {
      const blob = new Blob([JSON.stringify({ nodes, edges }, null, 2)], {
        type: "application/json",
      });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "graph.json";
      a.click();
    } else {
      const lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/graphml">',
        '<graph id="G" edgedefault="directed">',
      ];
      nodes.forEach((n) => {
        lines.push(
          `  <node id="${n.id}"><data key="name">${(n.name || "").replace(/&/g, "&amp;")}</data><data key="type">${n.type || ""}</data></node>`,
        );
      });
      edges.forEach((e, i) => {
        const src = typeof e.source === "object" ? e.source.id : e.source;
        const tgt = typeof e.target === "object" ? e.target.id : e.target;
        lines.push(
          `  <edge id="e${i}" source="${src}" target="${tgt}"><data key="type">${e.type}</data></edge>`,
        );
      });
      lines.push("</graph>", "</graphml>");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(
        new Blob([lines.join("\n")], { type: "application/xml" }),
      );
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

  useEffect(() => {
    const tooltipEl = tooltipRef.current;
    void redrawKey;
    if (!effectiveData || !tooltipEl) return;
    const filteredNodes = effectiveData.nodes
      .filter(
        (n) =>
          !tour.tourOpen ||
          nodeFilter === "全部" ||
          (n.type || n.label) === nodeFilter,
      )
      .filter((n) => limits.show_images || (n.type || n.label) !== "Image")
      .filter(
        (n) =>
          limits.show_entities ||
          ["Document", "Section", "Image", "Table"].includes(n.type || n.label),
      )
      .filter(
        (n) =>
          limits.show_level <= 0 ||
          (n.type || n.label) !== "Section" ||
          (n.level ?? 1) <= limits.show_level,
      )
      .filter((n) => limits.tbl > 0 || (n.type || n.label) !== "Table")
      .map((n) => ({ ...n, x: undefined, y: undefined }));
    const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = effectiveData.edges
      .filter(
        (e) =>
          (edgeFilter === "全部关系" || e.type === edgeFilter) &&
          filteredNodeIds.has(
            typeof e.source === "string" ? e.source : e.source.id,
          ) &&
          filteredNodeIds.has(
            typeof e.target === "string" ? e.target : e.target.id,
          ),
      )
      .map((e) => ({ ...e }));
    // Compute per-node edge counts from visible edges
    const nodeEdgeCounts = new Map<string, number>();
    for (const e of filteredEdges) {
      const src = typeof e.source === "string" ? e.source : e.source.id;
      const tgt = typeof e.target === "string" ? e.target : e.target.id;
      nodeEdgeCounts.set(src, (nodeEdgeCounts.get(src) ?? 0) + 1);
      nodeEdgeCounts.set(tgt, (nodeEdgeCounts.get(tgt) ?? 0) + 1);
    }
    let hiddenCount = 0;
    const displayNodes = hideIsolated
      ? filteredNodes.filter((n) => {
          if ((n.type || n.label) !== "Document") return true;
          if ((nodeEdgeCounts.get(n.id) ?? 0) > 0) return true;
          hiddenCount++;
          return false;
        })
      : filteredNodes;

    // View stats for panel
    const refEdgeCount = filteredEdges.filter(
      (e) => e.type === "REFERENCES",
    ).length;
    const visibleDocs = displayNodes.filter(
      (n) => (n.type || n.label) === "Document",
    );
    const noRefDocCount = visibleDocs.filter(
      (n) =>
        !filteredEdges.some(
          (e) =>
            e.type === "REFERENCES" &&
            ((typeof e.source === "string" ? e.source : e.source.id) === n.id ||
              (typeof e.target === "string" ? e.target : e.target.id) === n.id),
        ),
    ).length;
    setViewStats({
      docCount: visibleDocs.length,
      noRefDocCount,
      refEdgeCount,
      hiddenIsolated: hiddenCount,
    });

    filteredNodesRef.current = displayNodes;
    filteredEdgesRef.current = filteredEdges;
    if (pixiDestroyRef.current) {
      pixiDestroyRef.current();
      pixiDestroyRef.current = null;
    }
    const nc = filteredNodes.length;
    const autoMode: RenderMode =
      nc > 2000 ? "webgl" : nc > 500 ? "canvas" : "svg";
    const mode = manualMode ?? autoMode;
    setRenderMode(mode);
    let canceled = false;
    if (mode === "webgl" && webglRef.current && tooltipRef.current) {
      const wRef = webglRef.current,
        tRef = tooltipRef.current;
      import("pixi.js")
        .then((PIXI) => {
          if (canceled) return;
          drawGraphWebGL(
            PIXI,
            { nodes: filteredNodes, edges: filteredEdges },
            wRef,
            tRef,
            setScale,
            (node) => setSelectedNode(node),
            highlightedIds,
            heatMap,
            isDarkTheme,
          )
            .then(({ zoom, destroy }) => {
              pixiDestroyRef.current = destroy;
              if (canceled) {
                destroy();
                pixiDestroyRef.current = null;
                return;
              }
              zoomRef.current = zoom as unknown as d3.ZoomBehavior<
                Element,
                unknown
              >;
            })
            .catch(() => {});
        })
        .catch(() => {});
    } else if (mode === "canvas" && canvasRef.current) {
      zoomRef.current = drawGraphCanvas(
        { nodes: filteredNodes, edges: filteredEdges },
        canvasRef.current,
        tooltipEl,
        setScale,
        (node) => setSelectedNode(node),
        highlightedIds,
        heatMap,
        tour.tourOpen ? tour.tourNodeIds : undefined,
        tour.tourOpen ? tour.tourCurrentId : undefined,
        isDarkTheme,
        colorOverride.size > 0 ? colorOverride : undefined,
        userAnnotatedIds.size > 0 ? userAnnotatedIds : undefined,
      ) as unknown as d3.ZoomBehavior<Element, unknown>;
    } else if (svgRef.current) {
      zoomRef.current = drawGraph(
        { nodes: filteredNodes, edges: filteredEdges },
        svgRef.current,
        tooltipEl,
        setScale,
        (node) => setSelectedNode(node),
        highlightedIds,
        heatMap,
        tour.tourOpen ? tour.tourNodeIds : undefined,
        tour.tourOpen ? tour.tourCurrentId : undefined,
        isDarkTheme,
      ) as unknown as d3.ZoomBehavior<Element, unknown>;
    }
    return () => {
      canceled = true;
      if (pixiDestroyRef.current) {
        pixiDestroyRef.current();
        pixiDestroyRef.current = null;
      }
    };
  }, [
    effectiveData,
    nodeFilter,
    edgeFilter,
    highlightedIds,
    heatMap,
    colorOverride,
    userAnnotatedIds,
    manualMode,
    hideIsolated,
    tour.tourNodeIds,
    tour.tourCurrentId,
    tour.tourOpen,
    redrawKey,
    isDarkTheme,
    limits,
    canvasRef.current,
    svgRef.current,
    webglRef.current,
    tooltipRef.current,
  ]); // eslint-disable-line react-hooks/exhaustive-deps

  function onExpandAll(
    docFilterArg: string,
    showImages: boolean,
    showEntities: boolean,
    totalNodes: number,
  ) {
    if (
      totalNodes > 500 &&
      !confirm(
        `当前文档共有约 ${totalNodes} 个节点，全部展开可能影响性能，确认？`,
      )
    )
      return;
    const params = new URLSearchParams({
      limit_doc: "9999",
      limit_sec: "9999",
      limit_entity: "9999",
      limit_tbl: "0",
      doc_id: docFilterArg,
      show_level: "0",
      show_images: String(showImages),
      show_entities: String(showEntities),
      expand_all: "true",
    });
    fetchApi<GraphData>(`/api/graph?${params}`)
      .then((d: GraphData) => {
        loadedDocIdsRef.current = new Set(
          d.nodes
            .filter((node) => (node.type || node.label) === "Document")
            .map((node) => node.doc_id || node.id),
        );
        loadedSectionIdsRef.current = new Set(
          d.nodes
            .filter((node) => (node.type || node.label) === "Section")
            .map((node) => node.id),
        );
        replaceGraphData(d);
      })
      .catch(() => {});
  }

  return {
    containerRef,
    filteredNodesRef,
    zoomRef,
    renderMode,
    manualMode,
    setManualMode,
    scale,
    graphStats,
    heatMap,
    importanceMode,
    setImportanceMode,
    domainMode,
    setDomainMode,
    nodeFilter,
    setNodeFilter,
    edgeFilter,
    setEdgeFilter,
    selectedNode,
    setSelectedNode,
    searchQuery,
    docFilter,
    setDocFilter,
    docs,
    docSearchResults,
    nodeSearchResults,
    limits,
    setLimits,
    expandingId,
    showLimits,
    setShowLimits,
    showLegend,
    setShowLegend,
    showExport,
    setShowExport,
    copied,
    hideIsolated,
    setHideIsolated,
    viewStats,
    isDarkTheme,
    graphTheme,
    tour,
    zoomIn,
    zoomOut,
    zoomReset,
    focusNode,
    handleSearch,
    handleSelectNodeResult,
    handleSelectDocumentResult,
    expandSection,
    exportGraph,
    shareSnapshot,
    onExpandAll,
    showPredictions,
    setShowPredictions,
  };
}
