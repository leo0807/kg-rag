"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { addEdge, applyEdgeChanges, applyNodeChanges, type Connection, type EdgeChange, type NodeChange } from "reactflow";
import { fetchApi } from "@/lib/api";
import type { NodeTypeDef, ParamValue, PipelineConfig, PipelineEdge, PipelineNode } from "./types";
import { PRESETS } from "./presets";
import { useClipboard } from "./useClipboard";

export function usePipeline() {
  const [schema, setSchema] = useState<Record<string, NodeTypeDef>>({});
  const [configs, setConfigs] = useState<PipelineConfig[]>([]);
  const [activeConfigId, setActiveConfigId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<PipelineNode[]>([]);
  const [edges, setEdges] = useState<PipelineEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validateResult, setValidateResult] = useState<{ valid: boolean; errors: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nodeCounter = useRef(0);

  // Load schema + configs on mount
  useEffect(() => {
    fetchApi<{ node_types: Record<string, NodeTypeDef> }>("/api/pipeline/schema")
      .then((d) => setSchema(d.node_types))
      .catch(() => setError("加载节点定义失败"));
    loadConfigs();
  }, []);

  async function loadConfigs() {
    try {
      const list = await fetchApi<PipelineConfig[]>("/api/pipeline", { noLogout: true });
      setConfigs(list);
      const def = list.find((c) => c.is_default);
      if (def) {
        setActiveConfigId(def.id);
        loadConfig(def);
      }
    } catch (e: unknown) {
      // 401 → 未登录或 token 过期（不触发全局登出，显示空状态）
      // 其他错误 → 显示提示
      const status = (e as { status?: number })?.status;
      if (status !== 401) setError("加载配置列表失败");
    }
  }

  function loadConfig(cfg: PipelineConfig) {
    setNodes((cfg.nodes as PipelineNode[]) ?? []);
    setEdges((cfg.edges as PipelineEdge[]) ?? []);
    setSelectedNodeId(null);
    setValidateResult(null);
  }

  // React Flow handlers
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((ns) => applyNodeChanges(changes, ns)),
    [],
  );
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((es) => applyEdgeChanges(changes, es)),
    [],
  );
  const onConnect = useCallback(
    (connection: Connection) =>
      setEdges((es) =>
        addEdge({ ...connection, animated: true, style: { stroke: "#6366f1" } }, es),
      ),
    [],
  );

  // Add a node by type (called from drag-drop or click)
  function addNode(nodeType: string, position = { x: 200, y: 200 }) {
    const def = schema[nodeType];
    if (!def) return;
    const id = `${nodeType}_${++nodeCounter.current}`;
    const defaultParams = Object.fromEntries(
      Object.entries(def.params).map(([k, p]) => [k, p.default]),
    );
    const newNode: PipelineNode = {
      id,
      type: "pipelineNode",
      position,
      data: {
        nodeType,
        label: def.label,
        color: def.color,
        category: def.category,
        inputs: def.inputs,
        outputs: def.outputs,
        params: defaultParams,
      },
    };
    setNodes((ns) => [...ns, newNode]);
  }

  // Update a node's params
  function updateNodeParam(nodeId: string, key: string, value: ParamValue) {
    setNodes((ns) =>
      ns.map((n) =>
        n.id === nodeId
          ? { ...n, data: { ...n.data, params: { ...n.data.params, [key]: value } } }
          : n,
      ),
    );
  }

  // Delete selected node
  function deleteSelectedNode() {
    if (!selectedNodeId) return;
    setNodes((ns) => ns.filter((n) => n.id !== selectedNodeId));
    setEdges((es) => es.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId));
    setSelectedNodeId(null);
  }

  // Apply a preset
  function applyPreset(presetKey: string) {
    const preset = PRESETS[presetKey];
    if (!preset) return;
    setNodes(preset.nodes as PipelineNode[]);
    setEdges(preset.edges as PipelineEdge[]);
    setSelectedNodeId(null);
    setValidateResult(null);
  }

  // Validate
  async function validate() {
    setValidating(true);
    try {
      const result = await fetchApi<{ valid: boolean; errors: string[] }>(
        "/api/pipeline/validate",
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nodes, edges }), noLogout: true },
      );
      setValidateResult(result);
      if (result.valid) {
        toast.success("链路校验通过");
      } else {
        toast.error(`校验失败：${result.errors.join("；")}`);
      }
    } catch {
      toast.error("验证请求失败");
      setValidateResult({ valid: false, errors: ["验证请求失败"] });
    } finally {
      setValidating(false);
    }
  }

  function getUniqueName(baseName: string): string {
    const names = new Set(configs.map((c) => c.name));
    if (!names.has(baseName)) return baseName;
    let i = 2;
    while (names.has(`${baseName} ${i}`)) i++;
    return `${baseName} ${i}`;
  }

  // Save (update existing or create new)
  async function save(name?: string) {
    setSaving(true);
    try {
      const isNew = !activeConfigId || !!name;
      const rawName = name || "我的配置";
      const finalName = isNew ? getUniqueName(rawName) : rawName;
      if (isNew && finalName !== rawName) toast.info(`名称已改为"${finalName}"（避免重复）`);
      const body = { name: finalName, nodes, edges, params: {} };
      if (activeConfigId && !name) {
        const updated = await fetchApi<PipelineConfig>(
          `/api/pipeline/${activeConfigId}`,
          { method: "PUT", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body), noLogout: true },
        );
        setConfigs((cs) => cs.map((c) => (c.id === updated.id ? updated : c)));
        toast.success("链路配置已保存");
      } else {
        const created = await fetchApi<PipelineConfig>(
          "/api/pipeline",
          { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body), noLogout: true },
        );
        setConfigs((cs) => [...cs, created]);
        setActiveConfigId(created.id);
        await setDefault(created.id);
        toast.success(`已创建并保存"${created.name}"`);
      }
    } catch {
      toast.error("保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function setDefault(configId: string) {
    try {
      await fetchApi(`/api/pipeline/${configId}/set-default`, { method: "POST", noLogout: true });
      setConfigs((cs) => cs.map((c) => ({ ...c, is_default: c.id === configId })));
      setActiveConfigId(configId);
    } catch {
      toast.error("设置默认配置失败");
    }
  }

  async function deleteConfig(configId: string) {
    try {
      await fetchApi(`/api/pipeline/${configId}`, { method: "DELETE", noLogout: true });
      const remaining = configs.filter((c) => c.id !== configId);
      setConfigs(remaining);
      if (activeConfigId === configId) {
        const fallback = remaining[0] ?? null;
        if (fallback) {
          setActiveConfigId(fallback.id);
          loadConfig(fallback);
        } else {
          setActiveConfigId(null);
          setNodes([]);
          setEdges([]);
        }
      }
      toast.success("配置已删除");
    } catch {
      toast.error("删除配置失败");
    }
  }

  const { clearCanvas, copySelected, pasteClipboard, cutSelected, hasClipboard } = useClipboard(
    nodes, edges, setNodes, setEdges, setSelectedNodeId, setValidateResult, nodeCounter,
  );

  function newConfig() {
    setNodes([]);
    setEdges([]);
    setActiveConfigId(null);
    setSelectedNodeId(null);
    setValidateResult(null);
  }

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;

  return {
    schema, configs, activeConfigId, nodes, edges, selectedNode, selectedNodeId,
    saving, validating, validateResult, error,
    setActiveConfigId, loadConfig, loadConfigs,
    onNodesChange, onEdgesChange, onConnect,
    addNode, updateNodeParam, deleteSelectedNode,
    setSelectedNodeId, applyPreset, validate, save, setDefault, deleteConfig, newConfig,
    clearCanvas, copySelected, pasteClipboard, cutSelected, hasClipboard,
  };
}
