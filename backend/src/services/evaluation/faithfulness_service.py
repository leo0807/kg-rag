from __future__ import annotations

import asyncio
import uuid
from typing import Any

from ..infra.task_state import TaskState, get_task_state_store

_STORE_PREFIX = "eval:faithfulness:"
_store = get_task_state_store()

_SYSTEM_PROMPT = (
    "你是一个严格的答案忠实度审核员。"
    "你的任务是判断给定的回答是否完全基于提供的参考段落，不包含幻觉内容。"
)

_JUDGE_TMPL = """\
## 参考段落
{context}

## 问题
{question}

## 待审核回答
{answer}

## 审核要求
请逐句检查回答中的每个关键声明，判断它是否能从参考段落中找到依据。
输出格式（严格 JSON，不要多余文字）：
{{
  "faithful": true 或 false,
  "score": 0.0~1.0 之间的浮点数（1.0 表示完全忠实），
  "unsupported_claims": ["声明1", "声明2"]（列出无法从参考段落找到依据的声明，没有则为空数组）,
  "reason": "一句话总结"
}}"""


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _call_llm(messages: list[dict]) -> str:
    from ..ai.service import get_llm_service
    llm = get_llm_service()
    return llm.chat(messages)


def _parse_judge_output(raw: str) -> dict[str, Any]:
    import json, re
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {
        "faithful": False,
        "score": 0.0,
        "unsupported_claims": [],
        "reason": "解析失败",
    }


async def _run_faithfulness_task(
    task_id: str,
    rows: list[dict[str, Any]],
) -> None:
    key = f"{_STORE_PREFIX}{task_id}"
    _state = _store.get(key)
    task = _state.progress if _state else {}
    task["status"] = "running"
    task["started_at"] = _now()
    _store.update(key, status="running", progress=task)
    results: list[dict[str, Any]] = []

    try:
        for idx, row in enumerate(rows, start=1):
            task["current_question"] = row["question"][:120]

            context = "\n\n---\n\n".join(row["passages"][:8])
            prompt = _JUDGE_TMPL.format(
                context=context,
                question=row["question"],
                answer=row["answer"],
            )
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            raw = await asyncio.to_thread(_call_llm, messages)
            verdict = _parse_judge_output(raw)

            result_row = {
                "row_no": idx,
                "question": row["question"],
                "answer": row["answer"],
                "passages_count": len(row["passages"]),
                "faithful": verdict.get("faithful", False),
                "score": float(verdict.get("score", 0.0)),
                "unsupported_claims": verdict.get("unsupported_claims", []),
                "reason": verdict.get("reason", ""),
            }
            results.append(result_row)

            task["completed"] = idx
            task["faithful_count"] = sum(1 for r in results if r["faithful"])
            task["results_preview"] = results[-20:]
            _store.update(key, progress=task)
            await asyncio.sleep(0)

        total = len(results)
        faithful_count = task["faithful_count"]
        task["status"] = "completed"
        task["finished_at"] = _now()
        task["results"] = results
        task["results_preview"] = results[:50]
        task["summary"] = {
            "total": total,
            "faithful_count": faithful_count,
            "unfaithful_count": total - faithful_count,
            "faithfulness_rate": round(faithful_count / max(total, 1), 4),
            "avg_score": round(
                sum(r["score"] for r in results) / max(total, 1),
                4,
            ),
        }
        _store.update(key, status="completed", progress=task)
    except Exception as exc:
        task["status"] = "failed"
        task["finished_at"] = _now()
        task["error"] = str(exc)
        _store.update(key, status="failed", progress=task)


def _parse_rows(filename: str, data: bytes) -> list[dict[str, Any]]:
    """支持 JSONL（每行 {question, answer, passages:[...]}）或 CSV。"""
    import csv, io, json

    lower = filename.lower()
    if lower.endswith(".jsonl"):
        text = data.decode("utf-8-sig", errors="replace")
        raw_rows: list[dict] = []
        for i, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw_rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"第 {i} 行 JSONL 解析失败") from exc
    elif lower.endswith(".csv"):
        text = data.decode("utf-8-sig", errors="replace")
        raw_rows = list(csv.DictReader(io.StringIO(text)))
    else:
        raise ValueError("忠实度评测文件仅支持 .jsonl 或 .csv")

    rows: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_rows, start=1):
        question = (raw.get("question") or raw.get("问题") or "").strip()
        answer = (raw.get("answer") or raw.get("回答") or "").strip()
        passages_raw = raw.get("passages") or raw.get("段落") or []
        if isinstance(passages_raw, str):
            try:
                passages_raw = json.loads(passages_raw)
            except Exception:
                passages_raw = [passages_raw]
        passages = [str(p).strip() for p in passages_raw if str(p).strip()]

        if not question:
            continue
        if not answer:
            raise ValueError(f"第 {i} 行缺少 answer（回答）字段")
        if not passages:
            raise ValueError(f"第 {i} 行缺少 passages（参考段落）字段")

        rows.append({"question": question, "answer": answer, "passages": passages})

    if not rows:
        raise ValueError("忠实度评测文件没有可执行的数据行")
    return rows


def start_faithfulness_eval(
    filename: str,
    data: bytes,
) -> dict[str, Any]:
    rows = _parse_rows(filename, data)
    task_id = uuid.uuid4().hex
    key = f"{_STORE_PREFIX}{task_id}"
    initial_progress = {
        "task_id": task_id,
        "filename": filename,
        "status": "queued",
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "total": len(rows),
        "completed": 0,
        "faithful_count": 0,
        "current_question": "",
        "error": "",
        "summary": None,
        "results_preview": [],
        "results": [],
    }
    _store.set(key, TaskState(task_id=task_id, status="queued", progress=initial_progress))
    from ...tasks.eval_tasks import run_faithfulness_eval
    run_faithfulness_eval.delay(task_id=task_id, rows=rows)
    return get_faithfulness_task(task_id)


def get_faithfulness_task(task_id: str) -> dict[str, Any]:
    key = f"{_STORE_PREFIX}{task_id}"
    state = _store.get(key)
    if state is None:
        raise KeyError(task_id)
    return state.progress


def list_faithfulness_tasks(limit: int = 20) -> list[dict[str, Any]]:
    states = _store.list_by_prefix(_STORE_PREFIX, limit=max(limit, 1))
    return [s.progress for s in states]


def export_faithfulness_csv(task_id: str) -> str:
    import csv, io
    task = get_faithfulness_task(task_id)
    if task["status"] != "completed":
        raise ValueError("任务尚未完成，暂时不能导出")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["row_no", "faithful", "score", "question", "answer", "unsupported_claims", "reason"])
    for row in task["results"]:
        writer.writerow([
            row["row_no"],
            "YES" if row["faithful"] else "NO",
            row["score"],
            row["question"],
            row["answer"],
            " | ".join(row["unsupported_claims"]),
            row["reason"],
        ])
    return buf.getvalue()
