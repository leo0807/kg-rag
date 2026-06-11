"use client";
import { useEffect, useRef } from "react";
import * as d3 from "d3";

export type HierarchyNode = {
  id: string;
  name: string;
  type?: string;
  children?: HierarchyNode[];
};

type Props = { data: HierarchyNode | null; width?: number; height?: number };

const NODE_COLORS: Record<string, string> = {
  document: "#3B82F6",
  section:  "#10B981",
  entity:   "#F59E0B",
  default:  "#6B7280",
};

export function HierarchicalGraph({ data, width = 800, height = 500 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !data) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const root = d3.hierarchy(data);
    const tree = d3.tree<HierarchyNode>().size([height - 60, width - 160]);
    tree(root);

    const g = svg
      .append("g")
      .attr("transform", "translate(80,30)");

    // Links
    g.selectAll("path.link")
      .data(root.links())
      .join("path")
      .attr("class", "link")
      .attr("fill", "none")
      .attr("stroke", "#374151")
      .attr("stroke-width", 1.5)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .attr("d", (d3.linkHorizontal() as any)
        .x((d: d3.HierarchyPointNode<HierarchyNode>) => d.y)
        .y((d: d3.HierarchyPointNode<HierarchyNode>) => d.x));

    // Nodes
    const node = g.selectAll("g.node")
      .data(root.descendants())
      .join("g")
      .attr("class", "node")
      .attr("transform", d => `translate(${d.y},${d.x})`);

    node.append("circle")
      .attr("r", 5)
      .attr("fill", d => NODE_COLORS[d.data.type ?? "default"] ?? NODE_COLORS.default)
      .attr("stroke", "#1F2937")
      .attr("stroke-width", 1.5);

    node.append("text")
      .attr("dy", "0.35em")
      .attr("x", d => d.children ? -8 : 8)
      .attr("text-anchor", d => d.children ? "end" : "start")
      .attr("fill", "#D1D5DB")
      .attr("font-size", "11px")
      .text(d => d.data.name.length > 20 ? d.data.name.slice(0, 20) + "…" : d.data.name);
  }, [data, width, height]);

  if (!data) return (
    <div className="flex items-center justify-center bg-gray-900 rounded-lg border border-gray-800" style={{ width, height }}>
      <p className="text-gray-500 text-sm">暂无层级数据</p>
    </div>
  );

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 overflow-auto">
      <svg ref={svgRef} width={width} height={height} />
    </div>
  );
}
