"use client";

import { useState, useEffect, useRef } from "react";
import { 
  Play, 
  Pause, 
  Square, 
  RotateCcw, 
  Activity, 
  FileText, 
  AlertCircle, 
  CheckCircle2, 
  Loader2,
  Terminal,
  FolderOpen
} from "lucide-react";

interface IngestLog {
  time: string;
  level: "INFO" | "ERROR" | "SUCCESS" | "WARNING";
  msg: string;
}

interface BatchStatus {
  status: "idle" | "running" | "paused" | "stopping" | "completed" | "stopped";
  total: number;
  done: number;
  failed: number;
  current: string;
  logs: IngestLog[];
}

export default function BatchIngestPanel() {
  const [status, setStatus] = useState<BatchStatus | null>(null);
  const [directory, setDirectory] = useState("uploads/docs");
  const [loading, setLoading] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  const fetchStatus = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/admin/batch/status", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error("Failed to fetch batch status:", err);
    }
  };

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, 2000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [status?.logs]);

  const handleAction = async (action: string, body?: any) => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/admin/batch/${action}`, {
        method: "POST",
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
        body: body ? JSON.stringify(body) : undefined
      });
      if (!res.ok) {
        const error = await res.json();
        alert(error.detail || "操作失败");
      }
      fetchStatus();
    } catch (err) {
      alert("网络请求失败");
    } finally {
      setLoading(false);
    }
  };

  const percent = status?.total ? Math.round((status.done / status.total) * 100) : 0;

  return (
    <div className="flex-1 p-8 bg-gray-950 overflow-auto">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Activity className="text-indigo-500" />
              批量任务处理面板
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              管理大规模文档入库任务，支持断点续传与实时审计。
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <div className={`px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-2
                           ${status?.status === 'running' ? 'bg-indigo-500/10 text-indigo-400' : 
                             status?.status === 'paused' ? 'bg-amber-500/10 text-amber-400' :
                             status?.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' :
                             'bg-gray-800 text-gray-400'}`}>
              <div className={`w-2 h-2 rounded-full ${status?.status === 'running' ? 'bg-indigo-500 animate-pulse' : 
                                                     status?.status === 'paused' ? 'bg-amber-500' :
                                                     status?.status === 'completed' ? 'bg-emerald-500' : 'bg-gray-500'}`} />
              {status?.status || 'IDLE'}
            </div>
          </div>
        </div>

        {/* Controls Card */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl mb-8">
           <div className="flex flex-col md:flex-row gap-6 items-end">
              <div className="flex-1 space-y-2">
                 <label className="text-xs text-gray-500 font-bold uppercase tracking-wider flex items-center gap-2">
                    <FolderOpen size={14} />
                    扫描目录 (服务器路径)
                 </label>
                 <input 
                    type="text" 
                    value={directory}
                    onChange={(e) => setDirectory(e.target.value)}
                    disabled={status?.status === 'running' || status?.status === 'paused'}
                    className="w-full bg-gray-950 border border-gray-800 rounded-xl px-4 py-2.5 text-gray-200 
                             focus:ring-2 focus:ring-indigo-500 outline-none transition-all disabled:opacity-50"
                    placeholder="e.g. uploads/docs"
                 />
              </div>
              
              <div className="flex gap-2">
                {status?.status === 'idle' || status?.status === 'completed' || status?.status === 'stopped' ? (
                   <button 
                    onClick={() => handleAction('start', { directory })}
                    disabled={loading}
                    className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-indigo-600/20"
                   >
                     {loading ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                     开始扫描
                   </button>
                ) : (
                  <>
                    {status?.status === 'paused' ? (
                       <button 
                        onClick={() => handleAction('resume')}
                        className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-emerald-600/20"
                       >
                         <Play size={16} /> 恢复
                       </button>
                    ) : (
                      <button 
                        onClick={() => handleAction('pause')}
                        className="flex items-center gap-2 px-6 py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-amber-600/20"
                      >
                        <Pause size={16} /> 暂停
                      </button>
                    )}
                    <button 
                      onClick={() => handleAction('stop')}
                      className="flex items-center gap-2 px-6 py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-red-600/20"
                    >
                      <Square size={16} /> 停止
                    </button>
                  </>
                )}
              </div>
           </div>
        </div>

        {/* Progress Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
           <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <div className="text-xs text-gray-500 font-bold uppercase mb-4 flex items-center justify-between">
                任务进度
                <span className="text-indigo-400">{percent}%</span>
              </div>
              <div className="h-2 bg-gray-950 rounded-full overflow-hidden mb-4">
                 <div className="h-full bg-indigo-600 transition-all duration-500" style={{ width: `${percent}%` }} />
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">已完成: {status?.done}</span>
                <span className="text-gray-400">总数: {status?.total}</span>
              </div>
           </div>

           <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <div className="text-xs text-gray-500 font-bold uppercase mb-4">当前处理</div>
              <div className="flex items-center gap-3">
                 <div className="p-2 bg-indigo-500/10 rounded-lg shrink-0">
                    <FileText className="text-indigo-400" size={20} />
                 </div>
                 <div className="min-w-0">
                    <div className="text-sm font-bold text-gray-200 truncate">{status?.current || "等待中..."}</div>
                    <div className="text-[10px] text-gray-500 uppercase">处理中</div>
                 </div>
              </div>
           </div>

           <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
              <div className="text-xs text-gray-500 font-bold uppercase mb-4">异常计数</div>
              <div className="flex items-center gap-3">
                 <div className="p-2 bg-red-500/10 rounded-lg shrink-0">
                    <AlertCircle className="text-red-400" size={20} />
                 </div>
                 <div>
                    <div className="text-xl font-bold text-red-400">{status?.failed || 0}</div>
                    <div className="text-[10px] text-gray-500 uppercase">失败文件</div>
                 </div>
              </div>
           </div>
        </div>

        {/* Logs Panel */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden shadow-xl flex flex-col h-[400px]">
           <div className="px-6 py-4 border-b border-gray-800 bg-gray-950/50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                 <Terminal size={16} className="text-indigo-500" />
                 <h2 className="text-sm font-bold text-gray-200 uppercase tracking-widest">实时解析审计日志</h2>
              </div>
              <div className="text-[10px] text-gray-500">仅保留最近 100 条</div>
           </div>
           
           <div className="flex-1 overflow-auto p-4 font-mono text-xs space-y-1 bg-gray-950/30">
              {status?.logs && status.logs.length > 0 ? (
                status.logs.map((log, i) => (
                  <div key={i} className="flex gap-3 hover:bg-white/[0.02] py-0.5 px-2 rounded group">
                    <span className="text-gray-600 shrink-0">{log.time}</span>
                    <span className={`shrink-0 font-bold w-12 ${
                      log.level === 'ERROR' ? 'text-red-500' :
                      log.level === 'SUCCESS' ? 'text-emerald-500' :
                      log.level === 'WARNING' ? 'text-amber-500' : 'text-indigo-400'
                    }`}>
                      {log.level}
                    </span>
                    <span className="text-gray-400 group-hover:text-gray-200 transition-colors">{log.msg}</span>
                  </div>
                ))
              ) : (
                <div className="h-full flex flex-col items-center justify-center opacity-20">
                  <Loader2 size={32} className="animate-spin mb-2" />
                  <p>等待日志输出...</p>
                </div>
              )}
              <div ref={logEndRef} />
           </div>
        </div>
      </div>
    </div>
  );
}
