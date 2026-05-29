"""Unit tests for TaskStateStore (InMemory) + TaskState serialization."""
import time

import pytest

from src.services.infra.task_state import (
    InMemoryTaskStateStore,
    TaskState,
)


class TestInMemoryStore:

    def test_set_get_roundtrip(self):
        store = InMemoryTaskStateStore()
        state = TaskState(task_id="t1", status="queued")
        store.set("eval:obj:t1", state)

        retrieved = store.get("eval:obj:t1")
        assert retrieved is not None
        assert retrieved.task_id == "t1"
        assert retrieved.status == "queued"
        assert retrieved.created_at is not None
        assert retrieved.updated_at is not None

    def test_get_missing_returns_none(self):
        store = InMemoryTaskStateStore()
        assert store.get("nonexistent") is None

    def test_set_assigns_timestamps(self):
        store = InMemoryTaskStateStore()
        before = time.time()
        store.set("k", TaskState(task_id="x", status="queued"))
        after = time.time()
        s = store.get("k")
        assert s is not None
        assert before <= s.created_at <= after
        assert before <= s.updated_at <= after

    def test_set_preserves_existing_created_at(self):
        store = InMemoryTaskStateStore()
        state = TaskState(task_id="x", status="queued", created_at=1000.0)
        store.set("k", state)
        s = store.get("k")
        assert s.created_at == 1000.0

    def test_update_status(self):
        store = InMemoryTaskStateStore()
        store.set("t1", TaskState(task_id="t1", status="queued"))
        store.update("t1", status="running")
        assert store.get("t1").status == "running"

    def test_update_progress(self):
        store = InMemoryTaskStateStore()
        store.set("t1", TaskState(task_id="t1", status="queued"))
        store.update("t1", progress={"completed": 3, "total": 10})
        s = store.get("t1")
        assert s.progress == {"completed": 3, "total": 10}

    def test_update_missing_returns_none(self):
        store = InMemoryTaskStateStore()
        assert store.update("nonexistent", status="done") is None

    def test_update_bumps_updated_at(self):
        store = InMemoryTaskStateStore()
        store.set("t1", TaskState(task_id="t1", status="queued", created_at=1000.0))
        time.sleep(0.01)
        store.update("t1", status="running")
        s = store.get("t1")
        assert s.updated_at > 1000.0

    def test_update_unknown_field_is_ignored(self):
        store = InMemoryTaskStateStore()
        store.set("t1", TaskState(task_id="t1", status="queued"))
        store.update("t1", nonexistent_field="value")  # must not raise
        s = store.get("t1")
        assert not hasattr(s, "nonexistent_field")

    def test_delete(self):
        store = InMemoryTaskStateStore()
        store.set("t1", TaskState(task_id="t1", status="queued"))
        store.delete("t1")
        assert store.get("t1") is None

    def test_delete_missing_is_noop(self):
        store = InMemoryTaskStateStore()
        store.delete("nonexistent")  # must not raise

    def test_list_by_prefix_filters(self):
        store = InMemoryTaskStateStore()
        store.set("eval:obj:t1", TaskState(task_id="t1", status="queued"))
        store.set("eval:obj:t2", TaskState(task_id="t2", status="running"))
        store.set("eval:ds:t3", TaskState(task_id="t3", status="done"))
        store.set("scan:conflict:t4", TaskState(task_id="t4", status="done"))

        assert len(store.list_by_prefix("eval:obj:")) == 2
        assert len(store.list_by_prefix("eval:")) == 3
        assert len(store.list_by_prefix("scan:")) == 1

    def test_list_by_prefix_limit(self):
        store = InMemoryTaskStateStore()
        for i in range(20):
            store.set(f"ns:{i}", TaskState(task_id=str(i), status="done"))
        assert len(store.list_by_prefix("ns:", limit=5)) == 5

    def test_list_by_prefix_sorted_by_updated_at(self):
        store = InMemoryTaskStateStore()
        store.set("ns:old", TaskState(task_id="old", status="done", updated_at=1000.0))
        store.set("ns:new", TaskState(task_id="new", status="done", updated_at=9999.0))
        results = store.list_by_prefix("ns:")
        assert results[0].task_id == "new"

    def test_external_mutation_does_not_affect_store(self):
        store = InMemoryTaskStateStore()
        state = TaskState(task_id="t1", status="queued", progress={"step": 1})
        store.set("k", state)
        state.progress["step"] = 999  # mutate original
        assert store.get("k").progress["step"] == 1  # store unaffected


class TestTaskStateSerialization:

    def test_to_dict_from_dict_roundtrip(self):
        original = TaskState(
            task_id="abc",
            status="running",
            progress={"completed": 5, "total": 20},
            result=[{"row": 1, "answer": "A"}],
            error=None,
            metadata={"user_id": 100001},
            created_at=1234567890.0,
            updated_at=1234567900.0,
        )
        restored = TaskState.from_dict(original.to_dict())
        assert restored.task_id == original.task_id
        assert restored.status == original.status
        assert restored.progress == original.progress
        assert restored.result == original.result
        assert restored.metadata == original.metadata
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at

    def test_from_dict_ignores_unknown_keys(self):
        data = {
            "task_id": "x",
            "status": "done",
            "progress": {},
            "result": None,
            "error": None,
            "metadata": {},
            "created_at": None,
            "updated_at": None,
            "extra_future_field": "ignored",
        }
        s = TaskState.from_dict(data)
        assert s.task_id == "x"
        assert not hasattr(s, "extra_future_field")

    def test_json_serializable(self):
        import json
        state = TaskState(
            task_id="t1",
            status="completed",
            progress={"completed": 10, "total": 10},
            result=[{"q": "test", "a": "yes"}],
            metadata={"user_id": 42},
        )
        dumped = json.dumps(state.to_dict(), ensure_ascii=False)
        restored = TaskState.from_dict(json.loads(dumped))
        assert restored.task_id == "t1"
        assert restored.result[0]["q"] == "test"
