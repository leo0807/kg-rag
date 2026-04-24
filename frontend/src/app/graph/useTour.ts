"use client";

import { useState, useRef, useEffect } from "react";
import { getAuthHeaders } from "@/lib/api";
import type { GraphNode, GraphData, TourStop, NodeFilter } from "./constants";

const API = "http://localhost:8000";

export function useTour(
  zoomToNode: (id: string, delay?: number) => void,
  setNodeFilter: (f: NodeFilter) => void,
) {
  const [tourOpen, setTourOpen] = useState(false);
  const [tourTopic, setTourTopic] = useState("");
  const [tourRunning, setTourRunning] = useState(false);
  const [tourData, setTourData] = useState<GraphData | null>(null);
  const [tourStops, setTourStops] = useState<TourStop[]>([]);
  const [tourTotal, setTourTotal] = useState(0);
  const [tourIdx, setTourIdx] = useState(-1);
  const [tourText, setTourText] = useState("");
  const [tourStreaming, setTourStreaming] = useState(false);
  const [tourNodeIds, setTourNodeIds] = useState<Set<string>>(new Set());
  const [tourCurrentId, setTourCurrentId] = useState("");

  const tourIdxRef = useRef(-1);
  const tourTextRef = useRef("");
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(
    null,
  );

  useEffect(() => {
    tourIdxRef.current = tourIdx;
  }, [tourIdx]);

  async function startTour() {
    if (!tourTopic.trim() || tourRunning) return;
    setTourStops([]);
    setTourIdx(-1);
    setTourText("");
    setTourTotal(0);
    setTourNodeIds(new Set());
    setTourCurrentId("");
    setTourData(null);
    tourIdxRef.current = -1;
    tourTextRef.current = "";
    setTourRunning(true);
    setTourStreaming(false);
    setNodeFilter("全部");

    try {
      const headers = await getAuthHeaders({
        "Content-Type": "application/json",
      });
      const res = await fetch(`${API}/api/graph/tour`, {
        method: "POST",
        headers,
        body: JSON.stringify({ topic: tourTopic, max_stops: 6 }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body?.getReader();
      if (!reader) throw new Error("响应流为空");
      readerRef.current = reader;
      const decoder = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of decoder.decode(value).split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === "init") {
              setTourTotal(ev.total);
            } else if (ev.type === "path") {
              setTourData({ nodes: ev.nodes, edges: ev.edges });
              setTourNodeIds(new Set(ev.nodes.map((n: GraphNode) => n.id)));
            } else if (ev.type === "stop") {
              const idx = ev.index as number;
              tourIdxRef.current = idx;
              setTourIdx(idx);
              setTourCurrentId(ev.node_id);
              setTourText("");
              tourTextRef.current = "";
              setTourStreaming(true);
              setTourStops((prev) => [
                ...prev,
                {
                  index: idx,
                  node_id: ev.node_id,
                  node: ev.node,
                  explanation: "",
                },
              ]);
              zoomToNode(ev.node_id, idx === 0 ? 1800 : 400);
            } else if (ev.type === "delta") {
              tourTextRef.current += ev.content;
              const snapshot = tourTextRef.current;
              setTourText(snapshot);
              setTourStops((prev) =>
                prev.map((s) =>
                  s.index === tourIdxRef.current
                    ? { ...s, explanation: snapshot }
                    : s,
                ),
              );
            } else if (ev.type === "next_stop") {
              setTourStreaming(false);
            } else if (ev.type === "done" || ev.type === "error") {
              setTourStreaming(false);
              setTourRunning(false);
            }
          } catch {
            /* ignore parse errors */
          }
        }
      }
    } catch (e) {
      console.error("漫游失败:", e);
    } finally {
      setTourRunning(false);
      setTourStreaming(false);
    }
  }

  function stopTour() {
    readerRef.current?.cancel().catch(() => {});
    readerRef.current = null;
    setTourRunning(false);
    setTourStreaming(false);
    setTourData(null);
    setTourNodeIds(new Set());
    setTourCurrentId("");
    setTourIdx(-1);
    setTourStops([]);
    setTourText("");
  }

  function navigateTour(idx: number) {
    if (idx < 0 || idx >= tourStops.length) return;
    const stop = tourStops[idx];
    tourIdxRef.current = idx;
    setTourIdx(idx);
    setTourCurrentId(stop.node_id);
    setTourText(stop.explanation);
    tourTextRef.current = stop.explanation;
    zoomToNode(stop.node_id, 200);
  }

  return {
    tourOpen,
    setTourOpen,
    tourTopic,
    setTourTopic,
    tourRunning,
    tourData,
    tourStops,
    tourTotal,
    tourIdx,
    tourText,
    tourStreaming,
    tourNodeIds,
    tourCurrentId,
    hasPrev: tourIdx > 0,
    hasNext: tourIdx >= 0 && tourIdx < tourStops.length - 1 && !tourStreaming,
    startTour,
    stopTour,
    navigateTour,
  };
}
