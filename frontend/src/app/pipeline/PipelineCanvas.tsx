"use client";

import { type DragEvent, useCallback, useEffect, useRef } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type EdgeChange,
  type NodeChange,
  type Connection,
} from "reactflow";
import "reactflow/dist/style.css";
import { nodeTypes } from "./nodeTypes";
import type { PipelineEdge, PipelineNode } from "./types";

interface Props {
  nodes: PipelineNode[];
  edges: PipelineEdge[];
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  onNodeClick: (nodeId: string) => void;
  onAddNode: (nodeType: string, position: { x: number; y: number }) => void;
  onPaneClick: () => void;
  onCopy: () => void;
  onPaste: () => void;
  onCut: () => void;
}

export function PipelineCanvas({
  nodes, edges,
  onNodesChange, onEdgesChange, onConnect,
  onNodeClick, onAddNode, onPaneClick,
  onCopy, onPaste, onCut,
}: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const rfInstance = useRef<{ project: (pos: { x: number; y: number }) => { x: number; y: number } } | null>(null);

  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "c" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); onCopy(); }
      if (e.key === "v" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); onPaste(); }
      if (e.key === "x" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); onCut(); }
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, [onCopy, onPaste, onCut]);

  const onDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }, []);

  const onDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    const nodeType = e.dataTransfer.getData("application/pipeline-node");
    if (!nodeType || !wrapperRef.current || !rfInstance.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const position = rfInstance.current.project({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
    onAddNode(nodeType, position);
  }, [onAddNode]);

  return (
    <div ref={wrapperRef} className="flex-1" onDragOver={onDragOver} onDrop={onDrop}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, node) => onNodeClick(node.id)}
        onPaneClick={onPaneClick}
        onInit={(instance) => { rfInstance.current = instance as typeof rfInstance.current; }}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        deleteKeyCode="Delete"
        className="bg-gray-950"
      >
        <Background variant={BackgroundVariant.Dots} color="#374151" gap={20} size={1} />
        <Controls className="!bg-gray-900 !border-gray-700 !text-gray-300" />
        <MiniMap
          nodeColor={(n) => {
            const cat = n.data?.category;
            return cat === "retrieval" ? "#1B6BB5" : cat === "processing" ? "#D4820A" : "#5A9E28";
          }}
          className="!bg-gray-900 !border-gray-700"
        />
        {nodes.length === 0 && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="text-center text-sm text-gray-600">
              <div className="mb-2 text-3xl">⬡</div>
              从左侧节点库拖拽节点到此处，或点击节点添加
            </div>
          </div>
        )}
      </ReactFlow>
    </div>
  );
}
