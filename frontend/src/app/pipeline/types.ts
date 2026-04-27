import type { Node, Edge } from "reactflow";

export type ParamValue = number | string | boolean | string[];

export interface NodeParamDef {
  type: "int" | "float" | "string" | "select" | "multiselect" | "bool" | "text" | "textarea";
  default: ParamValue;
  min?: number;
  max?: number;
  options?: string[];
  label: string;
}

export interface NodeTypeDef {
  label: string;
  category: "retrieval" | "processing" | "generation" | "control";
  color: string;
  icon: string;
  inputs: string[];
  outputs: string[];
  params: Record<string, NodeParamDef>;
}

export interface PipelineNodeData {
  nodeType: string;
  label: string;
  color: string;
  category: string;
  inputs: string[];
  outputs: string[];
  params: Record<string, ParamValue>;
}

export type PipelineNode = Node<PipelineNodeData>;
export type PipelineEdge = Edge;

export interface PipelineConfig {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  nodes: object[];
  edges: object[];
  params: object;
  created_at: string;
  updated_at: string;
}

export const CATEGORY_LABELS: Record<string, string> = {
  retrieval:  "检索模块",
  processing: "处理模块",
  generation: "输出模块",
  control:    "控制模块",
};

export const CATEGORY_COLORS: Record<string, string> = {
  retrieval:  "bg-blue-500/20 text-blue-300 border-blue-500/30",
  processing: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  generation: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  control:    "bg-violet-500/20 text-violet-300 border-violet-500/30",
};
