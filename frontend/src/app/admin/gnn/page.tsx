"use client";
import React, { useState, useEffect, useCallback } from "react";
import { BrainCircuit, Play, RefreshCw, AlertCircle, CheckCircle2, Clock, ChevronDown, ChevronUp, HelpCircle, X } from "lucide-react";
import { fetchApi } from "@/lib/api";
import { Stat, ParamInput } from "./components";
import { StatusResponse, DEFAULT_PARAMS, formatTs } from "./types";

export default function GNNAdminPage() {
    const [status,      setStatus]      = useState<StatusResponse | null>(null);
    const [loading,     setLoading]     = useState(false);
    const [training,    setTraining]    = useState(false);
    const [params,      setParams]      = useState(DEFAULT_PARAMS);
    const [showParams,  setShowParams]  = useState(false);
    const [pollTimer,   setPollTimer]   = useState<ReturnType<typeof setInterval> | null>(null);
    const [showHelp,    setShowHelp]    = useState(false);

    const fetchStatus = useCallback(async () => {
        try {
            setStatus(await fetchApi<StatusResponse>(`/api/gnn/status`));
        } catch { /* ignore */ }
    }, []);

    useEffect(() => { fetchStatus(); }, [fetchStatus]);

    // Poll while training is running
    useEffect(() => {
        if (status?.training.running && !pollTimer) {
            const t = setInterval(fetchStatus, 2000);
            setPollTimer(t);
        } else if (!status?.training.running && pollTimer) {
            clearInterval(pollTimer);
            setPollTimer(null);
        }
        return () => { if (pollTimer) clearInterval(pollTimer); };
    }, [status?.training.running]);

    async function handleTrain() {
        setTraining(true);
        try {
            await fetchApi(`/api/gnn/train`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(params),
            });
            await fetchStatus();
        } catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            alert(`启动失败: ${msg}`);
        } finally {
            setTraining(false);
        }
    }

    async function handleRefresh() {
        setLoading(true);
        try {
            const s = await fetchApi(`/api/gnn/refresh`, { method: "POST" });
            setStatus(prev => prev ? { ...prev, service: s } : null);
        } finally {
            setLoading(false);
        }
    }

    const svc      = status?.service;
    const trainSt  = status?.training;
    const meta     = (svc?.metadata ?? {}) as Record<string, unknown>;

    return (
        <div className="min-h-screen bg-gray-950 text-gray-100 p-6 space-y-6">

            {/* 标题 */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <BrainCircuit size={24} className="text-violet-400" />
                    <div>
                        <h1 className="text-xl font-bold text-white">GNN 检索管理</h1>
                        <p className="text-sm text-gray-400 mt-0.5">
                            GraphSAGE 模型训练与 GNN 结构感知嵌入管理
                        </p>
                    </div>
                </div>
                <button
                    onClick={() => setShowHelp(v => !v)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm
                               text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700
                               border border-gray-700 transition-colors"
                >
                    <HelpCircle size={14} />
                    功能说明
                </button>
            </div>

            {/* 功能说明面板 */}
            {showHelp && (
                <div className="bg-violet-950/30 border border-violet-800/40 rounded-xl p-5 relative">
                    <button
                        onClick={() => setShowHelp(false)}
                        className="absolute top-3 right-3 text-gray-500 hover:text-white transition-colors"
                    >
                        <X size={14} />
                    </button>
                    <h3 className="text-sm font-semibold text-violet-300 mb-2">这个页面是做什么的？</h3>
                    <p className="text-sm text-gray-300 leading-relaxed mb-3">
                        这是一个"让系统变得更聪明"的训练页面。系统在回答问题时，
                        不仅会查找关键词，还会理解文档章节之间的关联关系——
                        例如「前处理」和「后处理」章节通常相邻出现。
                        GNN（图神经网络）训练就是让系统学习这些结构规律。
                    </p>
                    <div className="space-y-1.5 text-sm text-gray-400">
                        <div className="flex items-start gap-2">
                            <span className="text-violet-400 shrink-0 mt-0.5">①</span>
                            <span>首次使用前点击「开始训练」，训练一次即可（大约 5–20 分钟）。</span>
                        </div>
                        <div className="flex items-start gap-2">
                            <span className="text-violet-400 shrink-0 mt-0.5">②</span>
                            <span>训练结束后无需任何操作，系统会自动使用新模型。</span>
                        </div>
                        <div className="flex items-start gap-2">
                            <span className="text-violet-400 shrink-0 mt-0.5">③</span>
                            <span>当文档库有大量新增或删除时，建议重新训练一次以保持准确性。</span>
                        </div>
                    </div>
                </div>
            )}

            {/* 嵌入状态卡 */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                    <h2 className="font-semibold text-white">嵌入状态</h2>
                    <button
                        onClick={handleRefresh}
                        disabled={loading}
                        className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white
                                   bg-gray-800 hover:bg-gray-700 px-3 py-1.5 rounded-lg transition-colors"
                    >
                        <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
                        刷新加载
                    </button>
                </div>

                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <Stat label="加载状态"
                        value={svc?.loaded ? "已就绪" : "未加载"}
                        icon={svc?.loaded
                            ? <CheckCircle2 size={14} className="text-emerald-400" />
                            : <AlertCircle  size={14} className="text-amber-400" />}
                        accent={svc?.loaded ? "text-emerald-400" : "text-amber-400"}
                    />
                    <Stat label="节点数量"  value={svc?.num_nodes?.toLocaleString() ?? "—"} />
                    <Stat label="嵌入维度"  value={svc?.emb_dim   ? `${svc.emb_dim} 维` : "—"} />
                    <Stat label="训练损失"  value={meta.best_loss != null ? Number(meta.best_loss).toFixed(4) : "—"} />
                </div>

                {!!meta.trained_at && (
                    <div className="text-xs text-gray-500 pt-1 border-t border-gray-800">
                        上次训练: {formatTs(meta.trained_at as number)} &nbsp;·&nbsp;
                        {String(meta.epochs_run)} 轮 &nbsp;·&nbsp;
                        {Number(meta.num_edges).toLocaleString()} 条边 &nbsp;·&nbsp;
                        {Number(meta.num_pairs).toLocaleString()} 正样本对
                    </div>
                )}
            </div>

            {/* 训练控制 */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
                <h2 className="font-semibold text-white">训练 GraphSAGE</h2>

                {/* 训练进行中 */}
                {trainSt?.running && (
                    <div className="flex items-center gap-3 bg-violet-900/30 border border-violet-800/40
                                    rounded-lg px-4 py-3 text-sm text-violet-300">
                        <Clock size={14} className="animate-pulse flex-shrink-0" />
                        {trainSt.progress || "训练中..."}
                    </div>
                )}

                {/* 错误 */}
                {trainSt?.error && !trainSt.running && (
                    <div className="bg-red-900/20 border border-red-800/40 rounded-lg px-4 py-3
                                    text-xs text-red-400 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                        {trainSt.error}
                    </div>
                )}

                {/* 完成提示 */}
                {!trainSt?.running && !trainSt?.error && svc?.loaded && (
                    <div className="flex items-center gap-2 text-sm text-emerald-400">
                        <CheckCircle2 size={14} />
                        GNN 嵌入已加载，可在查询时使用 <code className="bg-gray-800 px-1.5 py-0.5 rounded text-xs">gnn</code> 策略
                    </div>
                )}

                {/* 参数折叠面板 */}
                <button
                    onClick={() => setShowParams(v => !v)}
                    className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors"
                >
                    {showParams ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    高级参数
                </button>

                {showParams && (
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 text-sm">
                        <ParamInput label="训练轮数 (epochs)" type="number" min={10}
                            value={params.epochs}
                            onChange={v => setParams(p => ({ ...p, epochs: Number(v) }))} />
                        <ParamInput label="学习率 (lr)" type="number" step="0.0001"
                            value={params.lr}
                            onChange={v => setParams(p => ({ ...p, lr: Number(v) }))} />
                        <ParamInput label="批大小 (batch_size)" type="number" min={32}
                            value={params.batch_size}
                            onChange={v => setParams(p => ({ ...p, batch_size: Number(v) }))} />
                        <ParamInput label="Dropout" type="number" step="0.05" min={0} max={0.5}
                            value={params.dropout}
                            onChange={v => setParams(p => ({ ...p, dropout: Number(v) }))} />
                        <ParamInput label="温度 (temperature)" type="number" step="0.01" min={0.01}
                            value={params.temperature}
                            onChange={v => setParams(p => ({ ...p, temperature: Number(v) }))} />
                        <ParamInput label="早停耐心 (patience)" type="number" min={5}
                            value={params.patience}
                            onChange={v => setParams(p => ({ ...p, patience: Number(v) }))} />
                        <div className="flex flex-col gap-1">
                            <label className="text-xs text-gray-400">设备 (device)</label>
                            <select
                                value={params.device}
                                onChange={e => setParams(p => ({ ...p, device: e.target.value }))}
                                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5
                                           text-sm text-white focus:outline-none focus:border-violet-500"
                            >
                                <option value="cpu">CPU</option>
                                <option value="cuda">CUDA (GPU)</option>
                            </select>
                        </div>
                    </div>
                )}

                <button
                    onClick={handleTrain}
                    disabled={training || trainSt?.running}
                    className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50
                               disabled:cursor-not-allowed text-white px-5 py-2 rounded-lg text-sm
                               font-medium transition-colors"
                >
                    <Play size={14} />
                    {trainSt?.running ? "训练中..." : "开始训练"}
                </button>
            </div>

            {/* 使用说明 */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
                <h2 className="font-semibold text-white">使用说明</h2>
                <ol className="text-sm text-gray-400 space-y-2 list-decimal list-inside">
                    <li>确保已导入文档（图谱中有 Section 节点和 Milvus 文本嵌入）</li>
                    <li>点击「开始训练」，后台运行 GraphSAGE 训练（约 5–20 分钟，取决于数据量）</li>
                    <li>训练完成后 GNN 嵌入自动热加载，无需重启服务</li>
                    <li>在智能问答中将检索策略切换为 <code className="bg-gray-800 px-1.5 py-0.5 rounded">gnn</code>，
                        即可享受结构感知检索（邻居类型分布 + 关系密度融入节点 Embedding）</li>
                </ol>
                <div className="mt-2 p-3 bg-gray-800/60 rounded-lg text-xs text-gray-500 space-y-1">
                    <div className="text-gray-300 font-medium mb-1">技术细节</div>
                    <div>• 节点特征: BGE-M3 文本嵌入 (1024 维) + 结构特征 (16 维: 实体数量、doc_type one-hot 等)</div>
                    <div>• 架构: 2 层 GraphSAGE，Mean 聚合，输出 1024 维 L2 归一化嵌入</div>
                    <div>• 邻接: HAS_SUBSECTION + NEXT_SECTION + 共享实体边 + SIMILAR_TO</div>
                    <div>• 训练目标: InfoNCE 对比损失，同文档章节为正样本对</div>
                    <div>• 检索: 用 BGE-M3 查询嵌入与 GNN 节点嵌入做内积（余弦相似度），再与全文检索 RRF 融合</div>
                </div>
            </div>
        </div>
    );
}

