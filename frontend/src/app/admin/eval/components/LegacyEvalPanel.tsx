"use client";

import { AbTestTab } from "./AbTestTab";
import { DatasetEvalTab } from "./DatasetEvalTab";
import { FaithfulnessTab } from "./FaithfulnessTab";
import { ObjectiveEvalTab } from "./ObjectiveEvalTab";
import { RetrievalEvalTab } from "./RetrievalEvalTab";
import { useEvalTasks } from "../useEvalTasks";

const LEGACY_TABS = [
  { id: "dataset", label: "数据集评测" },
  { id: "objective", label: "客观题评测" },
  { id: "retrieval", label: "检索评测" },
  { id: "faithfulness", label: "忠实度评测" },
  { id: "ab_test", label: "A/B 测试" },
] as const;

type LegacyTab = (typeof LEGACY_TABS)[number]["id"];

export function LegacyEvalPanel() {
  const {
    activeTab, setActiveTab,
    strategy, setStrategy, topK, setTopK,
    datasetTask, datasetStarting, objectiveTask, objectiveStarting,
    retrievalTask, retrievalStarting, retrievalStrategy, setRetrievalStrategy,
    faithfulnessTask, faithfulnessStarting, abTask, abStarting,
    error,
    setDatasetFile, setObjectiveFile, setRetrievalFile, setFaithfulnessFile, setAbFile,
    loadDatasetTask, loadObjectiveTask, loadRetrievalTask, loadFaithfulnessTask, loadAbTask,
    startDatasetEval, startObjectiveEval, startRetrievalEval, startFaithfulnessEval, startAbTest,
    downloadDatasetCsv, downloadObjectiveCsv, downloadRetrievalCsv, downloadFaithfulnessCsv, downloadAbCsv,
  } = useEvalTasks();

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-gray-700 pb-0">
        {LEGACY_TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as LegacyTab)}
            className={`px-4 py-2 text-sm rounded-t transition-colors ${
              activeTab === t.id
                ? "bg-gray-800 text-white border border-b-gray-800 border-gray-700"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === "dataset" && (
        <DatasetEvalTab strategy={strategy} topK={topK} task={datasetTask} starting={datasetStarting}
          error={error} onFileChange={setDatasetFile} onStrategyChange={setStrategy}
          onTopKChange={setTopK} onStart={startDatasetEval} onRefresh={loadDatasetTask}
          onDownloadCsv={downloadDatasetCsv} />
      )}
      {activeTab === "objective" && (
        <ObjectiveEvalTab task={objectiveTask} strategy={strategy} topK={topK}
          starting={objectiveStarting} error={error} onFileChange={setObjectiveFile}
          onStart={startObjectiveEval} onRefresh={loadObjectiveTask} onDownloadCsv={downloadObjectiveCsv} />
      )}
      {activeTab === "retrieval" && (
        <RetrievalEvalTab strategy={retrievalStrategy} topK={topK} task={retrievalTask}
          starting={retrievalStarting} error={error} onFileChange={setRetrievalFile}
          onStrategyChange={setRetrievalStrategy} onTopKChange={setTopK}
          onStart={startRetrievalEval} onRefresh={loadRetrievalTask} onDownloadCsv={downloadRetrievalCsv} />
      )}
      {activeTab === "faithfulness" && (
        <FaithfulnessTab task={faithfulnessTask} starting={faithfulnessStarting} error={error}
          onFileChange={setFaithfulnessFile} onStart={startFaithfulnessEval}
          onRefresh={loadFaithfulnessTask} onDownloadCsv={downloadFaithfulnessCsv} />
      )}
      {activeTab === "ab_test" && (
        <AbTestTab task={abTask} starting={abStarting} topK={topK} error={error}
          onFileChange={setAbFile} onTopKChange={setTopK} onStart={startAbTest}
          onRefresh={loadAbTask} onDownloadCsv={downloadAbCsv} />
      )}
    </div>
  );
}
