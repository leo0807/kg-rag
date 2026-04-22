from src.services.ops import runtime_service as svc


def test_list_runtime_tasks_normalizes_and_sorts(monkeypatch):
    monkeypatch.setattr(
        svc,
        "_load_runtime_sources",
        lambda: {
            "ingest": [
                {
                    "task_id": "ing-1",
                    "status": "running",
                    "created_at": "2026-04-22T10:00:00",
                    "step": "writing",
                    "doc_id": "CPS0200",
                }
            ],
            "reprocess": [
                {
                    "doc_id": "CPS1000",
                    "status": "completed",
                    "started_at": 1713770000,
                    "finished_at": 1713770300,
                    "message": "完成",
                }
            ],
            "dataset_eval": [],
            "objective_eval": [],
            "retrieval_eval": [
                {
                    "task_id": "ret-1",
                    "filename": "retrieval_cases.jsonl",
                    "status": "running",
                    "total": 10,
                    "completed": 4,
                    "created_at": "2026-04-22T11:00:00",
                    "current_question": "CPS0200 第一章范围讲的是什么？",
                }
            ],
            "batch_reprocess": [],
        },
    )

    items = svc.list_runtime_tasks(limit=10)

    assert items[0]["task_id"] == "ret-1"
    assert items[0]["progress"] == 0.4
    assert items[1]["task_id"] == "ing-1"
    assert items[2]["task_id"] == "CPS1000"
    assert items[2]["status"] == "completed"
