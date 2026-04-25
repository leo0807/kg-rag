"use client";

import { DatasetEvalTab } from "./components/DatasetEvalTab";
import { EvalTabHeader } from "./components/EvalTabHeader";
import { ObjectiveEvalTab } from "./components/ObjectiveEvalTab";
import { RetrievalEvalTab } from "./components/RetrievalEvalTab";
import { useEvalTasks } from "./useEvalTasks";

export default function AdminEvalPage() {
  const {
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
    error,
    setDatasetFile,
    setObjectiveFile,
    setRetrievalFile,
    loadDatasetTask,
    loadObjectiveTask,
    loadRetrievalTask,
    startDatasetEval,
    startObjectiveEval,
    startRetrievalEval,
    downloadDatasetCsv,
    downloadObjectiveCsv,
    downloadRetrievalCsv,
  } = useEvalTasks();

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
      <EvalTabHeader activeTab={activeTab} onTabChange={setActiveTab} />

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
          onDownloadCsv={downloadDatasetCsv}
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
          onDownloadCsv={downloadObjectiveCsv}
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
          onDownloadCsv={downloadRetrievalCsv}
        />
      )}
    </div>
  );
}
