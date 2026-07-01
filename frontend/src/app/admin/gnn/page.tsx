"use client";
import { useState, useEffect, useCallback } from "react";
import { BrainCircuit, CheckCircle2, ChevronDown, ChevronUp, Clock, HelpCircle, Play, RefreshCw } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { Stat, ParamInput } from "./components";
import type { GNNServiceStatus } from "./types";
import { StatusResponse, DEFAULT_PARAMS, formatTs } from "./types";
import { GNNHelpPanel } from "./GNNHelpPanel";
import { GNNInstructions } from "./GNNInstructions";

export default function GNNAdminPage() {
  const [status,     setStatus]     = useState<StatusResponse | null>(null);
  const [loading,    setLoading]    = useState(false);
  const [training,   setTraining]   = useState(false);
  const [params,     setParams]     = useState(DEFAULT_PARAMS);
  const [showParams, setShowParams] = useState(false);
  const [pollTimer,  setPollTimer]  = useState<ReturnType<typeof setInterval> | null>(null);
  const [showHelp,   setShowHelp]   = useState(false);

  const fetchStatus = useCallback(async () => {
    try { setStatus(await fetchApi<StatusResponse>(`/api/gnn/status`)); } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  useEffect(() => {
    if (status?.training.running && !pollTimer) {
      const t = setInterval(fetchStatus, 2000);
      setPollTimer(t);
    } else if (!status?.training.running && pollTimer) {
      clearInterval(pollTimer);
      setPollTimer(null);
    }
    return () => { if (pollTimer) clearInterval(pollTimer); };
  }, [status?.training.running]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleTrain() {
    setTraining(true);
    try {
      await fetchApi(`/api/gnn/train`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(params) });
      await fetchStatus();
    } catch (err) { alert(`启动失败: ${err instanceof Error ? err.message : String(err)}`); }
    finally { setTraining(false); }
  }

  async function handleRefresh() {
    setLoading(true);
    try {
      const s = await fetchApi<GNNServiceStatus>(`/api/gnn/refresh`, { method: "POST" });
      setStatus(prev => prev ? { ...prev, service: s } : null);
    } finally { setLoading(false); }
  }

  const svc     = status?.service;
  const trainSt = status?.training;
  const meta    = (svc?.metadata ?? {}) as Record<string, unknown>;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BrainCircuit size={24} className="text-violet-400" />
          <div>
            <h1 className="text-xl font-bold text-white">GNN 检索管理</h1>
            <p className="text-sm text-gray-400 mt-0.5">GraphSAGE 模型训练与 GNN 结构感知嵌入管理</p>
          </div>
        </div>
        <button onClick={() => setShowHelp(v => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 border border-gray-700 transition-colors">
          <HelpCircle size={14} /> 功能说明
        </button>
      </div>

      {showHelp && <GNNHelpPanel onClose={() => setShowHelp(false)} />}

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-white">嵌入状态</h2>
          <button onClick={handleRefresh} disabled={loading}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 px-3 py-1.5 rounded-lg transition-colors">
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> 刷新加载
          </button>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="加载状态" value={svc?.loaded ? "已就绪" : "未加载"}
            icon={svc?.loaded ? <CheckCircle2 size={14} className="text-emerald-400" /> : <Clock size={14} className="text-amber-400" />}
            accent={svc?.loaded ? "text-emerald-400" : "text-amber-400"} />
          <Stat label="节点数量" value={svc?.num_nodes?.toLocaleString() ?? "—"} />
          <Stat label="嵌入维度" value={svc?.emb_dim ? `${svc.emb_dim} 维` : "—"} />
          <Stat label="训练损失" value={meta.best_loss != null ? Number(meta.best_loss).toFixed(4) : "—"} />
        </div>
        {!!meta.trained_at && (
          <div className="text-xs text-gray-500 pt-1 border-t border-gray-800">
            上次训练: {formatTs(meta.trained_at as number)} · {String(meta.epochs_run)} 轮 ·{" "}
            {Number(meta.num_edges).toLocaleString()} 条边 · {Number(meta.num_pairs).toLocaleString()} 正样本对
          </div>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <h2 className="font-semibold text-white">训练 GraphSAGE</h2>
        {trainSt?.running && (
          <div className="flex items-center gap-3 bg-violet-900/30 border border-violet-800/40 rounded-lg px-4 py-3 text-sm text-violet-300">
            <Clock size={14} className="animate-pulse flex-shrink-0" /> {trainSt.progress || "训练中..."}
          </div>
        )}
        {trainSt?.error && !trainSt.running && (
          <div className="bg-red-900/20 border border-red-800/40 rounded-lg px-4 py-3 text-xs text-red-400 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
            {trainSt.error}
          </div>
        )}
        {!trainSt?.running && !trainSt?.error && svc?.loaded && (
          <div className="flex items-center gap-2 text-sm text-emerald-400">
            <CheckCircle2 size={14} />
            GNN 嵌入已加载，可在查询时使用 <code className="bg-gray-800 px-1.5 py-0.5 rounded text-xs">gnn</code> 策略
          </div>
        )}
        <button onClick={() => setShowParams(v => !v)}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors">
          {showParams ? <ChevronUp size={12} /> : <ChevronDown size={12} />} 高级参数
        </button>
        {showParams && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 text-sm">
            <ParamInput label="训练轮数 (epochs)" type="number" min={10} value={params.epochs} onChange={v => setParams(p => ({ ...p, epochs: Number(v) }))} />
            <ParamInput label="学习率 (lr)" type="number" step="0.0001" value={params.lr} onChange={v => setParams(p => ({ ...p, lr: Number(v) }))} />
            <ParamInput label="批大小 (batch_size)" type="number" min={32} value={params.batch_size} onChange={v => setParams(p => ({ ...p, batch_size: Number(v) }))} />
            <ParamInput label="Dropout" type="number" step="0.05" min={0} max={0.5} value={params.dropout} onChange={v => setParams(p => ({ ...p, dropout: Number(v) }))} />
            <ParamInput label="温度 (temperature)" type="number" step="0.01" min={0.01} value={params.temperature} onChange={v => setParams(p => ({ ...p, temperature: Number(v) }))} />
            <ParamInput label="早停耐心 (patience)" type="number" min={5} value={params.patience} onChange={v => setParams(p => ({ ...p, patience: Number(v) }))} />
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-400">设备 (device)</label>
              <select value={params.device} onChange={e => setParams(p => ({ ...p, device: e.target.value }))}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-violet-500">
                <option value="cpu">CPU</option>
                <option value="cuda">CUDA (GPU)</option>
              </select>
            </div>
          </div>
        )}
        <button onClick={handleTrain} disabled={training || trainSt?.running}
          className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors">
          <Play size={14} /> {trainSt?.running ? "训练中..." : "开始训练"}
        </button>
      </div>

      <GNNInstructions />
    </div>
  );
}
