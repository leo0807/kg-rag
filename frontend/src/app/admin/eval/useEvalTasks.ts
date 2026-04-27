"use client";

import { useEffect, useRef, useState } from "react";
import type { MutableRefObject } from "react";

import { fetchApi, getAuthHeaders } from "@/lib/api";

import type {
  AbTestTask,
  EvalTabKey,
  EvalTask,
  FaithfulnessTask,
  ObjectiveTask,
  RetrievalStrategy,
  RetrievalTask,
  Strategy,
} from "./types";

const API = "http://localhost:8000";

async function postForm<T>(url: string, formData: FormData): Promise<T> {
  const headers = await getAuthHeaders();
  const response = await fetch(url, { method: "POST", headers, body: formData });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "请求失败" }));
    throw new Error(body.detail || "请求失败");
  }
  return response.json();
}

function downloadWithAuth(url: string, filename: string, onError: (message: string) => void) {
  getAuthHeaders()
    .then((headers) => fetch(url, { headers }))
    .then((response) => {
      if (!response.ok) throw new Error("导出失败");
      return response.blob();
    })
    .then((blob) => {
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = href;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(href);
    })
    .catch((error) => onError(error instanceof Error ? error.message : "导出失败"));
}

export function useEvalTasks() {
  const [activeTab, setActiveTab] = useState<EvalTabKey>("dataset");
  const [strategy, setStrategy] = useState<Strategy>("parallel");
  const [topK, setTopK] = useState(5);

  const [datasetFile, setDatasetFile] = useState<File | null>(null);
  const [datasetTask, setDatasetTask] = useState<EvalTask | null>(null);
  const [datasetStarting, setDatasetStarting] = useState(false);

  const [objectiveFile, setObjectiveFile] = useState<File | null>(null);
  const [objectiveTask, setObjectiveTask] = useState<ObjectiveTask | null>(null);
  const [objectiveStarting, setObjectiveStarting] = useState(false);

  const [retrievalFile, setRetrievalFile] = useState<File | null>(null);
  const [retrievalStrategy, setRetrievalStrategy] = useState<RetrievalStrategy>("parallel");
  const [retrievalTask, setRetrievalTask] = useState<RetrievalTask | null>(null);
  const [retrievalStarting, setRetrievalStarting] = useState(false);

  const [faithfulnessFile, setFaithfulnessFile] = useState<File | null>(null);
  const [faithfulnessTask, setFaithfulnessTask] = useState<FaithfulnessTask | null>(null);
  const [faithfulnessStarting, setFaithfulnessStarting] = useState(false);

  const [abFile, setAbFile] = useState<File | null>(null);
  const [abTask, setAbTask] = useState<AbTestTask | null>(null);
  const [abStarting, setAbStarting] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const datasetTimerRef = useRef<number | null>(null);
  const objectiveTimerRef = useRef<number | null>(null);
  const retrievalTimerRef = useRef<number | null>(null);
  const faithfulnessTimerRef = useRef<number | null>(null);
  const abTimerRef = useRef<number | null>(null);

  function clearTimer(timerRef: MutableRefObject<number | null>) {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  async function loadDatasetTask(taskId: string) {
    const data = await fetchApi<EvalTask>(`${API}/api/admin/eval/dataset/${taskId}`);
    setDatasetTask(data);
    if (data.status === "completed" || data.status === "failed") clearTimer(datasetTimerRef);
  }

  async function loadObjectiveTask(taskId: string) {
    const data = await fetchApi<ObjectiveTask>(`${API}/api/admin/eval/objective-doc/${taskId}`);
    setObjectiveTask(data);
    if (data.status === "completed" || data.status === "failed") clearTimer(objectiveTimerRef);
  }

  async function loadRetrievalTask(taskId: string) {
    const data = await fetchApi<RetrievalTask>(`${API}/api/admin/eval/retrieval/${taskId}`);
    setRetrievalTask(data);
    if (data.status === "completed" || data.status === "failed") clearTimer(retrievalTimerRef);
  }

  async function loadFaithfulnessTask(taskId: string) {
    const data = await fetchApi<FaithfulnessTask>(`${API}/api/admin/eval/faithfulness/${taskId}`);
    setFaithfulnessTask(data);
    if (data.status === "completed" || data.status === "failed") clearTimer(faithfulnessTimerRef);
  }

  async function loadAbTask(taskId: string) {
    const data = await fetchApi<AbTestTask>(`${API}/api/admin/eval/ab-test/${taskId}`);
    setAbTask(data);
    if (data.status === "completed" || data.status === "failed") clearTimer(abTimerRef);
  }

  useEffect(() => {
    return () => {
      clearTimer(datasetTimerRef);
      clearTimer(objectiveTimerRef);
      clearTimer(retrievalTimerRef);
      clearTimer(faithfulnessTimerRef);
      clearTimer(abTimerRef);
    };
  }, []);

  async function startDatasetEval() {
    if (!datasetFile) {
      setError("请先选择测试集文件");
      return;
    }

    setDatasetStarting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", datasetFile);
      formData.append("strategy", strategy);
      formData.append("top_k", String(topK));

      const data = await postForm<EvalTask>(`${API}/api/admin/eval/dataset`, formData);
      setDatasetTask(data);
      setActiveTab("dataset");
      clearTimer(datasetTimerRef);
      datasetTimerRef.current = window.setInterval(() => {
        loadDatasetTask(data.task_id);
      }, 1500);
    } catch (error) {
      setError(error instanceof Error ? error.message : "启动评测失败");
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
      const formData = new FormData();
      formData.append("file", objectiveFile);
      formData.append("strategy", strategy);
      formData.append("top_k", String(topK));

      const data = await postForm<ObjectiveTask>(`${API}/api/admin/eval/objective-doc`, formData);
      setObjectiveTask(data);
      setActiveTab("objective");
      clearTimer(objectiveTimerRef);
      objectiveTimerRef.current = window.setInterval(() => {
        loadObjectiveTask(data.task_id);
      }, 1500);
    } catch (error) {
      setError(error instanceof Error ? error.message : "启动客观题测试失败");
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
      const formData = new FormData();
      formData.append("file", retrievalFile);
      formData.append("strategy", retrievalStrategy);
      formData.append("top_k", String(topK));

      const data = await postForm<RetrievalTask>(`${API}/api/admin/eval/retrieval`, formData);
      setRetrievalTask(data);
      setActiveTab("retrieval");
      clearTimer(retrievalTimerRef);
      retrievalTimerRef.current = window.setInterval(() => {
        loadRetrievalTask(data.task_id);
      }, 1500);
    } catch (error) {
      setError(error instanceof Error ? error.message : "启动检索评测失败");
    } finally {
      setRetrievalStarting(false);
    }
  }

  async function startFaithfulnessEval() {
    if (!faithfulnessFile) { setError("请先选择忠实度评测文件"); return; }
    setFaithfulnessStarting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", faithfulnessFile);
      const data = await postForm<FaithfulnessTask>(`${API}/api/admin/eval/faithfulness`, formData);
      setFaithfulnessTask(data);
      setActiveTab("faithfulness");
      clearTimer(faithfulnessTimerRef);
      faithfulnessTimerRef.current = window.setInterval(() => loadFaithfulnessTask(data.task_id), 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动忠实度评测失败");
    } finally {
      setFaithfulnessStarting(false);
    }
  }

  async function startAbTest(strategies: string[]) {
    if (!abFile) { setError("请先选择 A/B 测试文件"); return; }
    setAbStarting(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", abFile);
      formData.append("strategies", strategies.join(","));
      formData.append("top_k", String(topK));
      const data = await postForm<AbTestTask>(`${API}/api/admin/eval/ab-test`, formData);
      setAbTask(data);
      setActiveTab("ab_test");
      clearTimer(abTimerRef);
      abTimerRef.current = window.setInterval(() => loadAbTask(data.task_id), 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动 A/B 测试失败");
    } finally {
      setAbStarting(false);
    }
  }

  return {
    activeTab,
    setActiveTab,
    strategy,
    setStrategy,
    topK,
    setTopK,
    datasetTask,
    datasetStarting,
    objectiveTask,
    objectiveStarting,
    retrievalTask,
    retrievalStarting,
    retrievalStrategy,
    setRetrievalStrategy,
    faithfulnessTask,
    faithfulnessStarting,
    abTask,
    abStarting,
    error,
    setDatasetFile,
    setObjectiveFile,
    setRetrievalFile,
    setFaithfulnessFile,
    setAbFile,
    loadDatasetTask,
    loadObjectiveTask,
    loadRetrievalTask,
    loadFaithfulnessTask,
    loadAbTask,
    startDatasetEval,
    startObjectiveEval,
    startRetrievalEval,
    startFaithfulnessEval,
    startAbTest,
    downloadDatasetCsv() {
      if (!datasetTask) return;
      downloadWithAuth(
        `${API}/api/admin/eval/dataset/${datasetTask.task_id}/csv`,
        `${datasetTask.filename.replace(/\.(xlsx|csv)$/i, "")}_results.csv`,
        setError,
      );
    },
    downloadObjectiveCsv() {
      if (!objectiveTask) return;
      downloadWithAuth(
        `${API}/api/admin/eval/objective-doc/${objectiveTask.task_id}/csv`,
        `${objectiveTask.filename.replace(/\.(docx|doc|wps)$/i, "")}_predictions.csv`,
        setError,
      );
    },
    downloadRetrievalCsv() {
      if (!retrievalTask) return;
      downloadWithAuth(
        `${API}/api/admin/eval/retrieval/${retrievalTask.task_id}/csv`,
        `${retrievalTask.filename.replace(/\.(jsonl|csv)$/i, "")}_retrieval.csv`,
        setError,
      );
    },
    downloadFaithfulnessCsv() {
      if (!faithfulnessTask) return;
      downloadWithAuth(
        `${API}/api/admin/eval/faithfulness/${faithfulnessTask.task_id}/csv`,
        `${faithfulnessTask.filename.replace(/\.(jsonl|csv)$/i, "")}_faithfulness.csv`,
        setError,
      );
    },
    downloadAbCsv() {
      if (!abTask) return;
      downloadWithAuth(
        `${API}/api/admin/eval/ab-test/${abTask.task_id}/csv`,
        `${abTask.filename.replace(/\.(jsonl|csv)$/i, "")}_ab_test.csv`,
        setError,
      );
    },
  };
}
