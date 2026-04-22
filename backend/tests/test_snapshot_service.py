import json


def test_list_snapshots_migrates_legacy_files(tmp_path, monkeypatch):
    from src.services import snapshot_service as svc

    new_root = tmp_path / "uploads" / "snapshots"
    legacy_root = tmp_path / "snapshots"
    legacy_doc_dir = legacy_root / "CPS1000"
    legacy_doc_dir.mkdir(parents=True)
    payload = {
        "snapshot_id": "snap_123",
        "timestamp": 123,
        "constraints": [{}],
        "defects": [],
        "images": [],
    }
    (legacy_doc_dir / "snap_123.json").write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(svc, "SNAPSHOT_DIR", new_root)
    monkeypatch.setattr(svc, "LEGACY_SNAPSHOT_DIR", legacy_root)

    snapshots = svc.list_snapshots("CPS1000")

    assert snapshots[0]["snapshot_id"] == "snap_123"
    assert (new_root / "CPS1000" / "snap_123.json").exists()
    assert not (legacy_doc_dir / "snap_123.json").exists()

