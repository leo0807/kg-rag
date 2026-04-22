from pathlib import Path

from src.services import retrieval_harness_service as svc


def test_builtin_retrieval_cases_jsonl_is_parseable():
    sample_path = Path(__file__).resolve().parents[1] / "eval" / "retrieval_cases.jsonl"

    rows = svc._rows_from_upload(
        sample_path.name,
        sample_path.read_bytes(),
    )

    assert len(rows) >= 5
    assert all(row["question"] for row in rows)
    assert all(row["gold_chunk_ids"] or row["gold_doc_ids"] for row in rows)
