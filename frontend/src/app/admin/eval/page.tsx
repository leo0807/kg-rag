"use client";

import { BookOpenText, FileQuestion, SearchCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { fetchApi, getAuthHeaders } from "@/lib/api";
import { DatasetEvalTab } from "./components/DatasetEvalTab";
import { ObjectiveEvalTab } from "./components/ObjectiveEvalTab";
import { RetrievalEvalTab } from "./components/RetrievalEvalTab";
import type {
  EvalTabKey,
  EvalTask,
  ObjectiveTask,
  RetrievalStrategy,
  RetrievalTask,
  Strategy,
} from "./types";

const API = "http://localhost:8000";

const TABS: Array<{
  key: EvalTabKey;
  label: string;
  description: string;
  icon: typeof BookOpenText;
}> = [
  {
    key: "dataset",
    label: "问答标准集",
    description: "有标准答案的问答评测",
    icon: BookOpenText,
  },
  {
    key: "objective",
    label: "客观题文档",
    description: "无答案题库自动抽题作答",
    icon: FileQuestion,
  },
  {
    key: "retrieval",
    label: "检索 Harness",
    description: "只评检索命中与召回",
    icon: SearchCheck,
  },
];

async function postForm<T>(url: string, formData: FormData): Promise<T> {
  const headers = await getAuthHeaders();
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(body.detail || "请求失败");
  }
  return res.json();
}

function downloadWithAuth(
  url: string,
  filename: string,
  onError: (message: string) => void,
) {
  getAuthHeaders()
    .then((headers) => fetch(url, { headers }))
    .then((r) => {
      if (!r.ok) throw new Error("导出失败");
      return r.blob();
    })
    .then((blob) => {
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(href);
    })
    .catch((e) => onError(e instanceof Error ? e.message : "导出失败"));
}

export default function AdminEvalPage() {
  const [activeTab, setActiveTab] = useState<EvalTabKey>("dataset");
  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [strategy, setStrategy] = useState<Strategy>("parallel");
  const [topK, setTopK] = useState(5);
  const [datasetTask, setDatasetTask] = useState<EvalTask | null>(null);
  const [datasetStarting, setDatasetStarting] = useState(false);

  const [objectiveFile, setObjectiveFile] = useState<File | null>(null);
  const [objectiveTask, setObjectiveTask] = useState<ObjectiveTask | null>(
    null,
  );
  const [objectiveStarting, setObjectiveStarting] = useState(false);

  const [retrievalFile, setRetrievalFile] = useState<File | null>(null);
  const [retrievalStrategy, setRetrievalStrategy] =
    useState<RetrievalStrategy>("parallel");
  const [retrievalTask, setRetrievalTask] = useState<RetrievalTask | null>(
    null,
  );
  const [retrievalStarting, setRetrievalStarting] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const datasetTimerRef = useRef<number | null>(null);
  const objectiveTimerRef = useRef<number | null>(null);
  const retrievalTimerRef = useRef<number | null>(null);

  async function loadDatasetTask(taskId: string) {
    const data = await fetchApi<EvalTask>(
      `${API}/api/admin/eval/dataset/${taskId}`,
    );
    setDatasetTask(data);
    if (data.status === "completed" || data.status === "failed") {
      if (datasetTimerRef.current) {
        window.clearInterval(datasetTimerRef.current);
        datasetTimerRef.current = null;
      }
    }
  }

  async function loadObjectiveTask(taskId: string) {
    const data = await fetchApi<ObjectiveTask>(
      `${API}/api/admin/eval/objective-doc/${taskId}`,
    );
    setObjectiveTask(data);
    if (data.status === "completed" || data.status === "failed") {
      if (objectiveTimerRef.current) {
        window.clearInterval(objectiveTimerRef.current);
        objectiveTimerRef.current = null;
      }
    }
  }

  async function loadRetrievalTask(taskId: string) {
    const data = await fetchApi<RetrievalTask>(
      `${API}/api/admin/eval/retrieval/${taskId}`,
    );
    setRetrievalTask(data);
    if (data.status === "completed" || data.status === "failed") {
      if (retrievalTimerRef.current) {
        window.clearInterval(retrievalTimerRef.current);
        retrievalTimerRef.current = null;
      }
    }
  }

  useEffect(
    () => () => {
      if (datasetTimerRef.current)
        window.clearInterval(datasetTimerRef.current);
      if (objectiveTimerRef.current)
        window.clearInterval(objectiveTimerRef.current);
      if (retrievalTimerRef.current)
        window.clearInterval(retrievalTimerRef.current);
    },
    [],
  );

  async function startDatasetEval() {
    if (!datasetFile) {
      setError("请先选择测试集文件");
      return;
    }

    setDatasetStarting(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", datasetFile);
      fd.append("strategy", strategy);
      fd.append("top_k", String(topK));

      const data = await postForm<EvalTask>(
        `${API}/api/admin/eval/dataset`,
        fd,
      );
      setDatasetTask(data);
      setActiveTab("dataset");

      if (datasetTimerRef.current)
        window.clearInterval(datasetTimerRef.current);
      datasetTimerRef.current = window.setInterval(() => {
        loadDatasetTask(data.task_id);
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动评测失败");
    } finally {
      setDatasetStarting(false);
    }
  }

  async function startObjectiveEval() {
    if (!objectiveFile) {
      setError("请先选择客观题文档");
      return;
    }

    setObjectiveStarting(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", objectiveFile);
      fd.append("strategy", strategy);
      fd.append("top_k", String(topK));

      const data = await postForm<ObjectiveTask>(
        `${API}/api/admin/eval/objective-doc`,
        fd,
      );
      setObjectiveTask(data);
      setActiveTab("objective");

      if (objectiveTimerRef.current)
        window.clearInterval(objectiveTimerRef.current);
      objectiveTimerRef.current = window.setInterval(() => {
        loadObjectiveTask(data.task_id);
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动客观题测试失败");
    } finally {
      setObjectiveStarting(false);
    }
  }

  async function startRetrievalEval() {
    if (!retrievalFile) {
      setError("请先选择检索评测文件");
      return;
    }

    setRetrievalStarting(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", retrievalFile);
      fd.append("strategy", retrievalStrategy);
      fd.append("top_k", String(topK));

      const data = await postForm<RetrievalTask>(
        `${API}/api/admin/eval/retrieval`,
        fd,
      );
      setRetrievalTask(data);
      setActiveTab("retrieval");

      if (retrievalTimerRef.current)
        window.clearInterval(retrievalTimerRef.current);
      retrievalTimerRef.current = window.setInterval(() => {
        loadRetrievalTask(data.task_id);
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动检索评测失败");
    } finally {
      setRetrievalStarting(false);
    }
  }

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
      <div className="rounded-3xl border border-gray-800 bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.16),transparent_40%),radial-gradient(circle_at_top_right,rgba(16,185,129,0.10),transparent_36%),#111827] p-6">
        <div className="max-w-3xl">
          <h1 className="text-2xl font-semibold text-white">测试集评测</h1>
          <p className="mt-2 text-sm leading-6 text-gray-400">
            三类评测已内置到同一页签中。问答标准集和检索 Harness
            都提供了可直接上传的标准模板，
            用户只要保留字段名不变，按模板改内容就能直接使用。
          </p>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`group rounded-2xl border px-4 py-3 text-left transition-all ${
                  active
                    ? "border-indigo-500 bg-indigo-500/15 shadow-[0_0_0_1px_rgba(99,102,241,0.28)]"
                    : "border-gray-800 bg-gray-900/70 hover:border-gray-700 hover:bg-gray-900"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Icon
                    size={15}
                    className={
                      active
                        ? "text-indigo-300"
                        : "text-gray-500 group-hover:text-gray-300"
                    }
                  />
                  <span className={active ? "text-white" : "text-gray-300"}>
                    {tab.label}
                  </span>
                </div>
                <div className="mt-1 text-xs text-gray-500">
                  {tab.description}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {activeTab === "dataset" && (
        <DatasetEvalTab
          strategy={strategy}
          topK={topK}
          task={datasetTask}
          starting={datasetStarting}
          error={error}
          onFileChange={setDatasetFile}
          onStrategyChange={setStrategy}
          onTopKChange={setTopK}
          onStart={startDatasetEval}
          onRefresh={loadDatasetTask}
          onDownloadCsv={() => {
            if (!datasetTask) return;
            downloadWithAuth(
              `${API}/api/admin/eval/dataset/${datasetTask.task_id}/csv`,
              `${datasetTask.filename.replace(/\.(xlsx|csv)$/i, "")}_results.csv`,
              setError,
            );
          }}
        />
      )}

      {activeTab === "objective" && (
        <ObjectiveEvalTab
          task={objectiveTask}
          strategy={strategy}
          topK={topK}
          starting={objectiveStarting}
          error={error}
          onFileChange={setObjectiveFile}
          onStart={startObjectiveEval}
          onRefresh={loadObjectiveTask}
          onDownloadCsv={() => {
            if (!objectiveTask) return;
            downloadWithAuth(
              `${API}/api/admin/eval/objective-doc/${objectiveTask.task_id}/csv`,
              `${objectiveTask.filename.replace(/\.(docx|doc|wps)$/i, "")}_predictions.csv`,
              setError,
            );
          }}
        />
      )}

      {activeTab === "retrieval" && (
        <RetrievalEvalTab
          strategy={retrievalStrategy}
          topK={topK}
          task={retrievalTask}
          starting={retrievalStarting}
          error={error}
          onFileChange={setRetrievalFile}
          onStrategyChange={setRetrievalStrategy}
          onTopKChange={setTopK}
          onStart={startRetrievalEval}
          onRefresh={loadRetrievalTask}
          onDownloadCsv={() => {
            if (!retrievalTask) return;
            downloadWithAuth(
              `${API}/api/admin/eval/retrieval/${retrievalTask.task_id}/csv`,
              `${retrievalTask.filename.replace(/\.(jsonl|csv)$/i, "")}_retrieval.csv`,
              setError,
            );
          }}
        />
      )}
    </div>
  );
}
