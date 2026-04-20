#!/usr/bin/env python3
"""
backfill_section_level.py
为已入库的 Section 节点补充 level / number 属性，并建立 HAS_SUBSECTION 父子关系。

运行方式（在 backend/ 目录下）：
  python ../scripts/backfill_section_level.py
"""
import logging
import os
import sys
from pathlib import Path

SCRIPT_DIR  = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "aviation123")

BATCH_SIZE = 500


def _parse_level(chunk_id: str) -> tuple[str, int]:
    """
    从 chunk_id 解析 number 和 level。
    chunk_id 格式为 {doc_id}_{number}，如 CPS0210_1.2.3。
    doc_id 可能包含数字（如 CPS0210），number 是最后一个 _ 之后的部分。
    """
    # doc_id 格式固定为 CPS\d+（末尾可能有版本字母），number 是 _ 后的章节号
    # 策略：从右侧切分，取最后一段作为 number（章节号格式 \d+(\.\d+)*）
    import re
    # 找最后一个 _ 位置
    idx = chunk_id.rfind("_")
    if idx == -1:
        return "", 1
    number = chunk_id[idx + 1:]
    # 验证是否是合法章节号
    if not re.match(r'^\d{1,2}(\.\d{1,2}){0,3}$', number):
        return number, 1
    level = len(number.split("."))
    return number, level


def main():
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # ── 1. 查询所有 Section 节点 ────────────────────────────────────────────────
    log.info("查询所有 Section 节点...")
    with driver.session() as s:
        total_n = s.run("MATCH (s:Section) RETURN count(s) AS n").single()["n"]

    log.info("共 %d 个 Section 节点，批大小=%d", total_n, BATCH_SIZE)

    # ── 2. 分批更新 level / number ─────────────────────────────────────────────
    updated   = 0
    skipped   = 0
    offset    = 0

    while offset < total_n:
        with driver.session() as s:
            rows = list(s.run(
                "MATCH (sec:Section) RETURN sec.chunk_id AS chunk_id "
                "ORDER BY sec.chunk_id SKIP $skip LIMIT $limit",
                skip=offset, limit=BATCH_SIZE,
            ))

        batch_data = []
        for row in rows:
            cid = row["chunk_id"]
            if not cid:
                skipped += 1
                continue
            number, level = _parse_level(cid)
            if not number:
                skipped += 1
                continue
            batch_data.append({"chunk_id": cid, "number": number, "level": level})

        if batch_data:
            with driver.session() as s:
                s.run(
                    """
                    UNWIND $items AS item
                    MATCH (sec:Section {chunk_id: item.chunk_id})
                    SET sec.number = item.number,
                        sec.level  = item.level
                    """,
                    items=batch_data,
                )
            updated += len(batch_data)

        offset += BATCH_SIZE
        print(f"\r  进度: {min(offset, total_n)}/{total_n} ({min(offset, total_n)*100//total_n}%)",
              end="", flush=True)

    print()
    log.info("level/number 更新完成：updated=%d  skipped=%d", updated, skipped)

    # ── 3. 建立 HAS_SUBSECTION 父子关系 ────────────────────────────────────────
    log.info("建立 HAS_SUBSECTION 父子关系...")

    # 查询所有 level >= 2 的 Section（需要找父节点）
    with driver.session() as s:
        child_rows = list(s.run(
            """
            MATCH (d:Document)-[:HAS_SECTION]->(child:Section)
            WHERE child.level >= 2
            RETURN child.chunk_id AS cid, child.number AS number, d.name AS doc_id
            """
        ))

    log.info("需要建立父子关系的章节数: %d", len(child_rows))

    # 批量建立关系
    pairs      = []
    no_parent  = 0

    for row in child_rows:
        cid     = row["cid"]
        number  = row["number"]
        doc_id  = row["doc_id"]
        parts   = number.split(".")
        parent_number  = ".".join(parts[:-1])
        parent_chunk   = f"{doc_id}_{parent_number}"
        pairs.append({"parent_id": parent_chunk, "child_id": cid})

    # 分批写入
    rel_created = 0
    for i in range(0, len(pairs), BATCH_SIZE):
        chunk = pairs[i : i + BATCH_SIZE]
        with driver.session() as s:
            result = s.run(
                """
                UNWIND $pairs AS p
                MATCH (parent:Section {chunk_id: p.parent_id})
                MATCH (child:Section  {chunk_id: p.child_id})
                MERGE (parent)-[:HAS_SUBSECTION]->(child)
                RETURN count(*) AS n
                """,
                pairs=chunk,
            )
            n = result.single()
            rel_created += n["n"] if n else 0
        print(f"\r  HAS_SUBSECTION: {min(i + BATCH_SIZE, len(pairs))}/{len(pairs)}",
              end="", flush=True)

    print()
    log.info("HAS_SUBSECTION 关系建立完成: %d 条", rel_created)
    no_parent = len(pairs) - rel_created
    if no_parent:
        log.info("  （其中 %d 条因父节点不存在而跳过）", no_parent)

    # ── 4. 统计层级分布 ────────────────────────────────────────────────────────
    log.info("统计层级分布...")
    with driver.session() as s:
        dist = list(s.run(
            "MATCH (sec:Section) RETURN sec.level AS level, count(sec) AS cnt "
            "ORDER BY sec.level"
        ))

    driver.close()

    # ── 报告 ──────────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("补全完成报告")
    print("=" * 50)
    print(f"  更新节点数:    {updated}")
    print(f"  跳过节点数:    {skipped}")
    print(f"  建立关系数:    {rel_created}")
    print()
    print("各层级章节数量分布：")
    for row in dist:
        bar = "█" * min(int(row["cnt"] / 50), 40)
        print(f"  level={row['level']}  {row['cnt']:>5d}  {bar}")
    print("=" * 50)


if __name__ == "__main__":
    main()
