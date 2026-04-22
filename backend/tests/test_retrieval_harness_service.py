import asyncio

import pytest

from src.services import retrieval_harness_service as svc


@pytest.fixture(autouse=True)
def clear_tasks():
    svc._tasks.clear()
    svc.DO_RETRIEVAL = None
    yield
    svc._tasks.clear()
    svc.DO_RETRIEVAL = None


def test_rows_from_upload_supports_jsonl_and_csv():
    jsonl_rows = svc._rows_from_upload(
        "cases.jsonl",
        (
            '{"question":"Q1","gold_chunk_ids":["DOC_1"],"domain":"A"}\n'
            '{"question":"Q2","gold_doc_ids":"CPS0200|CPS0201","strategy":"parallel"}\n'
        ).encode("utf-8"),
    )
    csv_rows = svc._rows_from_upload(
        "cases.csv",
        (
            "问题,gold_chunk_ids,gold_doc_ids,专业\n"
            "Q1,DOC_1,,液压\n"
            "Q2,,CPS0200|CPS0201,复材\n"
        ).encode("utf-8"),
    )

    assert jsonl_rows[0]["gold_chunk_ids"] == ["DOC_1"]
    assert jsonl_rows[1]["gold_doc_ids"] == ["CPS0200", "CPS0201"]
    assert csv_rows[0]["domain"] == "液压"
    assert csv_rows[1]["gold_doc_ids"] == ["CPS0200", "CPS0201"]


def test_rows_from_upload_requires_gold_labels():
    with pytest.raises(ValueError, match="缺少 gold_chunk_ids 或 gold_doc_ids"):
        svc._rows_from_upload(
            "cases.jsonl",
            b'{"question":"Q1"}\n',
        )


def test_run_task_computes_chunk_and_doc_metrics(monkeypatch):
    def fake_retrieval(driver, question, strategy, top_k, use_hyde=False, hyde_alpha=0.5, doc_id=""):
        if question == "chunk":
            return (
                [
                    {"chunk_id": "DOC_9", "doc_id": "CPS9999", "number": "9", "title": "noise"},
                    {"chunk_id": "DOC_1", "doc_id": "CPS0200", "number": "1", "title": "范围"},
                ],
                {},
            )
        return (
            [
                {"chunk_id": "X_1", "doc_id": "CPS0202", "number": "3", "title": "要求"},
                {"chunk_id": "X_2", "doc_id": "CPS0201", "number": "6", "title": "性能"},
            ],
            {},
        )

    monkeypatch.setattr(svc, "DO_RETRIEVAL", fake_retrieval)
    task_id = "task-1"
    svc._tasks[task_id] = {
        "task_id": task_id,
        "filename": "cases.jsonl",
        "status": "queued",
        "strategy": "parallel",
        "top_k": 3,
        "created_at": "now",
        "started_at": None,
        "finished_at": None,
        "total": 2,
        "completed": 0,
        "matched": 0,
        "unmatched": 0,
        "current_question": "",
        "error": "",
        "summary": None,
        "results_preview": [],
        "results": [],
    }

    asyncio.run(
        svc._run_task(
            task_id,
            [
                {
                    "row_no": 1,
                    "question": "chunk",
                    "gold_chunk_ids": ["DOC_1"],
                    "gold_doc_ids": [],
                    "domain": "",
                    "strategy": "",
                    "doc_id": "",
                },
                {
                    "row_no": 2,
                    "question": "doc",
                    "gold_chunk_ids": [],
                    "gold_doc_ids": ["CPS0201"],
                    "domain": "",
                    "strategy": "",
                    "doc_id": "",
                },
            ],
            "parallel",
            3,
            driver=None,
        ),
    )

    task = svc.get_retrieval_task(task_id)
    assert task["status"] == "completed"
    assert task["matched"] == 2
    assert task["summary"]["hit_rate"] == 1.0
    assert task["summary"]["avg_recall"] == 1.0
    assert task["summary"]["mrr"] == 0.5
    assert task["results"][0]["hit_rank"] == 2
    assert task["results"][1]["target_type"] == "doc"


def test_start_retrieval_harness_rejects_invalid_strategy():
    with pytest.raises(ValueError, match="仅支持"):
        asyncio.run(
            svc.start_retrieval_harness(
                filename="cases.jsonl",
                data=b'{"question":"Q1","gold_chunk_ids":["DOC_1"]}\n',
                strategy="multi_hop",
                top_k=5,
                driver=None,
            ),
        )


def test_export_retrieval_task_csv():
    svc._tasks["done"] = {
        "task_id": "done",
        "status": "completed",
        "results": [
            {
                "row_no": 1,
                "domain": "液压",
                "strategy": "parallel",
                "target_type": "chunk",
                "question": "Q1",
                "matched": True,
                "hit_rank": 1,
                "recall": 1.0,
                "reciprocal_rank": 1.0,
                "gold_chunk_ids": ["DOC_1"],
                "gold_doc_ids": [],
                "retrieved_chunk_ids": ["DOC_1"],
                "retrieved_doc_ids": ["CPS0200"],
                "source_refs": ["CPS0200 §1"],
            }
        ],
    }

    text = svc.export_retrieval_task_csv("done")

    assert "target_type" in text
    assert "PASS" in text
    assert "CPS0200 §1" in text
