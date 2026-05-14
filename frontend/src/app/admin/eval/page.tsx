"use client";

import { AbTestTab } from "./components/AbTestTab";
import { DatasetEvalTab } from "./components/DatasetEvalTab";
import { EvalTabHeader } from "./components/EvalTabHeader";
import { FaithfulnessTab } from "./components/FaithfulnessTab";
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
    objectiveDocId,
    setObjectiveDocId,
    objectiveFileName,
    objectiveCanStart,
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
    downloadDatasetCsv,
    downloadObjectiveCsv,
    downloadRetrievalCsv,
    downloadFaithfulnessCsv,
    downloadAbCsv,
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
          docId={objectiveDocId}
          selectedFileName={objectiveFileName}
          canStart={objectiveCanStart}
          starting={objectiveStarting}
          error={error}
          onFileChange={setObjectiveFile}
          onDocIdChange={setObjectiveDocId}
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

      {activeTab === "faithfulness" && (
        <FaithfulnessTab
          task={faithfulnessTask}
          starting={faithfulnessStarting}
          error={error}
          onFileChange={setFaithfulnessFile}
          onStart={startFaithfulnessEval}
          onRefresh={loadFaithfulnessTask}
          onDownloadCsv={downloadFaithfulnessCsv}
        />
      )}

      {activeTab === "ab_test" && (
        <AbTestTab
          task={abTask}
          starting={abStarting}
          topK={topK}
          error={error}
          onFileChange={setAbFile}
          onTopKChange={setTopK}
          onStart={startAbTest}
          onRefresh={loadAbTask}
          onDownloadCsv={downloadAbCsv}
        />
      )}
    </div>
  );
}
