"""
快照服务 — 重新处理前保存图谱状态，支持回滚

存储路径:
  本地（主）: uploads/snapshots/{doc_id}/snap_{timestamp}.json
  兼容旧路径: snapshots/{doc_id}/snap_{timestamp}.json
  MinIO（备）: snapshots/{doc_id}/snap_{timestamp}.json

每文档保留最近 MAX_SNAPSHOTS 份快照
"""
import json
import logging
import time
import contextlib
from pathlib import Path

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path("uploads") / "snapshots"
LEGACY_SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
MAX_SNAPSHOTS = 3


# ── MinIO 备份（内部工具）────────────────────────────────────────────────────

def _backup_to_minio(doc_id: str, snapshot_id: str, data: bytes) -> None:
    """将快照字节上传到 MinIO snapshots 桶，失败时仅记录警告不抛出。"""
    try:
        from ..core.storage import upload_bytes, BUCKET_SNAPSHOTS
        key = f"{doc_id}/{snapshot_id}.json"
        upload_bytes(BUCKET_SNAPSHOTS, key, data, content_type="application/json")
        logger.debug("快照已备份到 MinIO: %s", key)
    except Exception as e:
        logger.warning("快照 MinIO 备份失败（本地仍有效）doc_id=%s id=%s: %s", doc_id, snapshot_id, e)


def _snapshot_key(doc_id: str, snapshot_id: str) -> str:
    return f"{doc_id}/{snapshot_id}.json"


def _migrate_legacy_snapshots(doc_id: str = "") -> None:
    """将旧的 snapshots/ 迁移到 uploads/snapshots/，迁移失败时仅记录日志。"""
    source_root = LEGACY_SNAPSHOT_DIR / doc_id if doc_id else LEGACY_SNAPSHOT_DIR
    if not source_root.exists():
        return

    for src in source_root.rglob("snap_*.json"):
        try:
            rel = src.relative_to(LEGACY_SNAPSHOT_DIR)
            dest = SNAPSHOT_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                src.unlink(missing_ok=True)
                continue
            src.replace(dest)
        except Exception as exc:
            logger.warning("迁移旧快照失败 %s: %s", src, exc)

    for maybe_dir in sorted(source_root.rglob("*"), reverse=True):
        if maybe_dir.is_dir():
            with contextlib.suppress(OSError):
                maybe_dir.rmdir()
    if not doc_id:
        with contextlib.suppress(OSError):
            LEGACY_SNAPSHOT_DIR.rmdir()


def _local_snapshot_path(doc_id: str, snapshot_id: str) -> Path:
    return SNAPSHOT_DIR / doc_id / f"{snapshot_id}.json"


def _legacy_snapshot_path(doc_id: str, snapshot_id: str) -> Path:
    return LEGACY_SNAPSHOT_DIR / doc_id / f"{snapshot_id}.json"


def _read_snapshot_bytes(doc_id: str, snapshot_id: str) -> bytes:
    local_path = _local_snapshot_path(doc_id, snapshot_id)
    if local_path.exists():
        return local_path.read_bytes()

    legacy_path = _legacy_snapshot_path(doc_id, snapshot_id)
    if legacy_path.exists():
        data = legacy_path.read_bytes()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        legacy_path.unlink(missing_ok=True)
        return data

    try:
        from ..core.storage import download_bytes, BUCKET_SNAPSHOTS
        data = download_bytes(BUCKET_SNAPSHOTS, _snapshot_key(doc_id, snapshot_id))
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        return data
    except Exception as exc:
        raise FileNotFoundError(f"快照不存在: {snapshot_id}") from exc


def _list_snapshot_ids_from_minio(doc_id: str) -> set[str]:
    try:
        from ..core.storage import list_files, BUCKET_SNAPSHOTS
        ids: set[str] = set()
        for key in list_files(BUCKET_SNAPSHOTS, prefix=f"{doc_id}/"):
            name = Path(key).name
            if name.startswith("snap_") and name.endswith(".json"):
                ids.add(name[:-5])
        return ids
    except Exception:
        return set()


# ── 公开 API ──────────────────────────────────────────────────────────────────

def take_snapshot(driver, doc_id: str) -> str:
    """拍摄当前文档图谱状态，返回 snapshot_id"""
    _migrate_legacy_snapshots(doc_id)
    snap_dir = SNAPSHOT_DIR / doc_id
    snap_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    snapshot_id = f"snap_{ts}"

    data = {
        "doc_id":           doc_id,
        "snapshot_id":      snapshot_id,
        "timestamp":        ts,
        "constraints":      _q_constraints(driver, doc_id),
        "defects":          _q_defects(driver, doc_id),
        "images":           _q_image_fields(driver, doc_id),
        "entity_relations": _q_entity_relations(driver, doc_id),
    }
    serialized = json.dumps(data, ensure_ascii=False, indent=2).encode()
    path = snap_dir / f"{snapshot_id}.json"
    path.write_bytes(serialized)
    _cleanup(snap_dir)
    logger.info("快照已保存 doc_id=%s id=%s", doc_id, snapshot_id)

    # MinIO 备份（异步不阻塞，失败不影响主流程）
    _backup_to_minio(doc_id, snapshot_id, serialized)

    return snapshot_id


def list_snapshots(doc_id: str) -> list[dict]:
    """返回可用快照列表（降序）"""
    _migrate_legacy_snapshots(doc_id)
    snap_dir = SNAPSHOT_DIR / doc_id
    result = []
    local_files = {f.stem: f for f in snap_dir.glob("snap_*.json")} if snap_dir.exists() else {}
    for snapshot_id in _list_snapshot_ids_from_minio(doc_id):
        if snapshot_id not in local_files:
            try:
                _read_snapshot_bytes(doc_id, snapshot_id)
            except FileNotFoundError:
                continue
    local_files = {f.stem: f for f in snap_dir.glob("snap_*.json")} if snap_dir.exists() else {}
    for f in sorted(local_files.values(), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "snapshot_id":       data["snapshot_id"],
                "timestamp":         data["timestamp"],
                "constraints_count": len(data.get("constraints", [])),
                "defects_count":     len(data.get("defects", [])),
                "images_count":      len(data.get("images", [])),
            })
        except Exception as e:
            logger.warning("读取快照失败 %s: %s", f.name, e)
    return result


def rollback(driver, doc_id: str, snapshot_id: str) -> dict:
    """从指定快照回滚文档图谱状态"""
    _migrate_legacy_snapshots(doc_id)
    data = json.loads(_read_snapshot_bytes(doc_id, snapshot_id).decode("utf-8"))
    counts = _restore(driver, doc_id, data)
    logger.info("回滚完成 doc_id=%s id=%s counts=%s", doc_id, snapshot_id, counts)
    return {"snapshot_id": snapshot_id, "restored": counts}


# ── 快照查询 ───────────────────────────────────────────────────────────────────

def _q_constraints(driver, doc_id: str) -> list[dict]:
    with driver.session() as s:
        return [
            {"props": dict(r["props"]), "chunk_id": r["chunk_id"]}
            for r in s.run(
                "MATCH (c:Constraint) WHERE c.doc_id = $d "
                "OPTIONAL MATCH (sec:Section)-[:HAS_CONSTRAINT]->(c) "
                "RETURN c {.*} AS props, sec.chunk_id AS chunk_id",
                d=doc_id,
            )
        ]


def _q_defects(driver, doc_id: str) -> list[dict]:
    with driver.session() as s:
        return [
            {"props": dict(r["props"]), "image_id": r["image_id"]}
            for r in s.run(
                "MATCH (d:Defect) WHERE d.doc_id = $d "
                "OPTIONAL MATCH (d)-[:DETECTED_IN]->(i:Image) "
                "RETURN d {.*} AS props, i.image_id AS image_id",
                d=doc_id,
            )
        ]


def _q_image_fields(driver, doc_id: str) -> list[dict]:
    with driver.session() as s:
        return [dict(r) for r in s.run("""
            MATCH (doc:Document {name: $d})-[:HAS_SECTION]->(sec:Section)
            OPTIONAL MATCH (sec)-[:HAS_IMAGE]->(i:Image)
            WHERE i IS NOT NULL
            RETURN i.image_id          AS image_id,
                   i.is_drawing        AS is_drawing,
                   i.part_numbers      AS part_numbers,
                   i.annotations       AS annotations,
                   i.assembly_relations AS assembly_relations,
                   i.drawing_summary   AS drawing_summary
        """, d=doc_id)]


def _q_entity_relations(driver, doc_id: str) -> list[dict]:
    with driver.session() as s:
        return [dict(r) for r in s.run("""
            MATCH (doc:Document {name: $d})-[:HAS_SECTION]->(sec:Section)
            MATCH (sec)-[r]->(e)
            WHERE e:Tool OR e:Material OR e:Process
            RETURN sec.chunk_id AS chunk_id, type(r) AS rel_type,
                   labels(e)[0] AS entity_type, e.name AS entity_name
        """, d=doc_id)]


# ── 恢复 ──────────────────────────────────────────────────────────────────────

def _restore(driver, doc_id: str, data: dict) -> dict:
    counts: dict[str, int] = {}

    # Constraints
    with driver.session() as s:
        s.run("MATCH (c:Constraint) WHERE c.doc_id = $d DETACH DELETE c", d=doc_id)
    constraints = data.get("constraints", [])
    with driver.session() as s:
        for item in constraints:
            p, cid = item["props"], item["props"].get("constraint_id", "")
            chunk_id = item.get("chunk_id") or ""
            s.run("MERGE (c:Constraint {constraint_id:$cid}) SET c=$p "
                  "WITH c OPTIONAL MATCH (sec:Section {chunk_id:$cid2}) "
                  "FOREACH(_ IN CASE WHEN sec IS NOT NULL THEN [1] ELSE [] END | MERGE (sec)-[:HAS_CONSTRAINT]->(c))",
                  cid=cid, p=p, cid2=chunk_id)
    counts["constraints"] = len(constraints)

    # Defects
    with driver.session() as s:
        s.run("MATCH (d:Defect) WHERE d.doc_id = $d DETACH DELETE d", d=doc_id)
    defects = data.get("defects", [])
    with driver.session() as s:
        for item in defects:
            p, did = item["props"], item["props"].get("defect_id", "")
            iid = item.get("image_id") or ""
            s.run("MERGE (d:Defect {defect_id:$did}) SET d=$p "
                  "WITH d OPTIONAL MATCH (i:Image {image_id:$iid}) "
                  "FOREACH(_ IN CASE WHEN i IS NOT NULL THEN [1] ELSE [] END | MERGE (d)-[:DETECTED_IN]->(i))",
                  did=did, p=p, iid=iid)
    counts["defects"] = len(defects)

    # Image drawing fields
    images = data.get("images", [])
    with driver.session() as s:
        for img in images:
            s.run("""MATCH (i:Image {image_id:$iid})
                SET i.is_drawing=$is_d, i.part_numbers=$pn,
                    i.annotations=$ann, i.assembly_relations=$ar,
                    i.drawing_summary=$ds""",
                iid=img.get("image_id"), is_d=img.get("is_drawing"),
                pn=img.get("part_numbers","[]"), ann=img.get("annotations","[]"),
                ar=img.get("assembly_relations","[]"), ds=img.get("drawing_summary",""),
            )
    counts["images"] = len(images)

    # Entity relations
    with driver.session() as s:
        s.run("""MATCH (doc:Document {name:$d})-[:HAS_SECTION]->(sec:Section)
            MATCH (sec)-[r]->(e) WHERE e:Tool OR e:Material OR e:Process DELETE r""", d=doc_id)
    rels = data.get("entity_relations", [])
    _LABELS = {"Tool": "Tool", "Material": "Material", "Process": "Process"}
    with driver.session() as s:
        for rel in rels:
            lb = _LABELS.get(rel.get("entity_type", ""))
            if lb:
                s.run(f"MATCH (sec:Section{{chunk_id:$cid}}) MERGE (e:{lb}{{name:$name}}) MERGE (sec)-[:{rel['rel_type']}]->(e)",
                      cid=rel["chunk_id"], name=rel["entity_name"])
    counts["entity_relations"] = len(rels)
    return counts


def _cleanup(snap_dir: Path):
    for old in sorted(snap_dir.glob("snap_*.json"), reverse=True)[MAX_SNAPSHOTS:]:
        old.unlink(missing_ok=True)
