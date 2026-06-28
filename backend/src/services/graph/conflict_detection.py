"""
Graph integrity and conflict detection services.

- Constraint conflict detection (same component, contradicting values)
- Dangling reference scanning
- Cycle detection in PRECEDES/FOLLOWS chains
- Graph integrity validation
- Version consistency checking
"""
from __future__ import annotations

import logging
from typing import Any

from ...core.database import get_driver

log = logging.getLogger(__name__)


# ─── Constraint Conflict Detection ────────────────────────────────────────────

def detect_constraint_conflicts(component_id: str | None = None) -> list[dict]:
    """
    Find Constraint nodes on the same Component that have conflicting values.
    If component_id is given, limit to that component.
    """
    driver = get_driver()
    cypher = """
        MATCH (c1:Constraint)<-[:HAS_CONSTRAINT]-(sec1:Section),
              (c2:Constraint)<-[:HAS_CONSTRAINT]-(sec2:Section)
        WHERE c1.parameter = c2.parameter
          AND c1.unit = c2.unit
          AND c1 <> c2
          AND (sec1)-[:APPLIES_TO]->(comp:Component)<-[:APPLIES_TO]-(sec2)
          AND abs(toFloat(c1.value) - toFloat(c2.value)) /
              (abs(toFloat(c1.value)) + 0.001) > 0.1
        RETURN comp.part_no AS component,
               c1.parameter AS parameter,
               c1.value AS value_a, sec1.chunk_id AS source_a, sec1.doc_id AS doc_a,
               c2.value AS value_b, sec2.chunk_id AS source_b, sec2.doc_id AS doc_b
        ORDER BY component, parameter
    """
    params: dict[str, Any] = {}
    if component_id:
        cypher = cypher.replace(
            "WHERE c1.parameter",
            "WHERE comp.part_no = $cid AND c1.parameter"
        )
        params["cid"] = component_id

    with driver.session() as s:
        result = s.run(cypher, **params)
        conflicts = [dict(r) for r in result]

    # Auto-write CONFLICTS_WITH edges for discovered pairs
    if conflicts:
        with driver.session() as s:
            for c in conflicts:
                s.run(
                    """
                    MATCH (a:Section {chunk_id: $a}), (b:Section {chunk_id: $b})
                    MERGE (a)-[:CONFLICTS_WITH {
                        parameter: $param,
                        value_a: $va, value_b: $vb
                    }]->(b)
                    """,
                    a=c["source_a"], b=c["source_b"],
                    param=c["parameter"],
                    va=str(c["value_a"]), vb=str(c["value_b"]),
                )

    return conflicts


# ─── Process Integrity Validation ────────────────────────────────────────────

def validate_process_integrity() -> dict[str, list[dict]]:
    """
    Check for isolated sections with no entity associations.
    Returns dict of issue categories → list of affected nodes.
    """
    driver = get_driver()
    issues: dict[str, list[dict]] = {}

    with driver.session() as s:
        # Sections with no Tool/Material/Process links
        r = s.run(
            """
            MATCH (sec:Section)
            WHERE NOT (sec)-[:REQUIRES_TOOL|USES_MATERIAL|HAS_PROCESS]->()
              AND NOT (sec:Section)-[:HAS_CONSTRAINT]->()
            RETURN sec.chunk_id AS chunk_id, sec.title AS title,
                   sec.doc_id AS doc_id
            LIMIT 100
            """
        )
        issues["no_entity_links"] = [dict(row) for row in r]

        # Sections referenced in REFERENCES but not present
        r2 = s.run(
            """
            MATCH (src:Section)-[:REFERENCES]->(ref)
            WHERE NOT exists(ref.chunk_id) AND NOT exists(ref.name)
            RETURN src.chunk_id AS chunk_id, src.title AS title,
                   src.doc_id AS doc_id
            LIMIT 50
            """
        )
        issues["broken_references"] = [dict(row) for row in r2]

    return issues


# ─── Dangling Reference Scan ──────────────────────────────────────────────────

def scan_dangling_references() -> list[dict]:
    """
    Find REFERENCES edges where the target Document is not in the graph.
    """
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (src:Document)-[:REFERENCES]->(target)
            WHERE NOT (target:Document) OR NOT exists(target.name)
            RETURN src.name AS source_doc,
                   coalesce(target.name, target.chunk_id, 'unknown') AS target_ref
            ORDER BY source_doc
            """
        )
        return [dict(r) for r in result]


# ─── Cycle Detection ──────────────────────────────────────────────────────────

def detect_cycles_in_precedes() -> list[dict]:
    """
    Detect cycles in the PRECEDES/FOLLOWS step chain.
    Returns list of cycle participants.
    """
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH path = (s:Step)-[:PRECEDES*2..10]->(s)
            RETURN [n IN nodes(path) | n.step_id] AS cycle_nodes
            LIMIT 20
            """
        )
        return [dict(r) for r in result]


# ─── Version Consistency Check ────────────────────────────────────────────────

def check_version_consistency(doc_id: str) -> list[dict]:
    """
    Compare Constraint values between successive document versions.
    Returns drifted parameters.
    """
    driver = get_driver()
    with driver.session() as s:
        result = s.run(
            """
            MATCH (new:Document {name: $doc_id})-[:SUPERSEDES]->(old:Document)
            MATCH (new)-[:HAS_SECTION]->(ns:Section)-[:HAS_CONSTRAINT]->(nc:Constraint)
            MATCH (old)-[:HAS_SECTION]->(os:Section)-[:HAS_CONSTRAINT]->(oc:Constraint)
            WHERE nc.parameter = oc.parameter
              AND nc.unit = oc.unit
              AND nc.value <> oc.value
            RETURN nc.parameter AS parameter,
                   oc.value AS old_value, nc.value AS new_value,
                   nc.unit AS unit,
                   ns.chunk_id AS new_section, os.chunk_id AS old_section
            ORDER BY parameter
            """,
            doc_id=doc_id,
        )
        return [dict(r) for r in result]


# ─── Graph Health Summary ─────────────────────────────────────────────────────

def graph_health_summary() -> dict[str, Any]:
    """Return six-metric health dashboard snapshot."""
    driver = get_driver()
    with driver.session() as s:
        # Isolated nodes
        isolated = s.run(
            "MATCH (n:Section) WHERE NOT (n)--() RETURN count(n) AS cnt"
        ).single()["cnt"]

        # Dangling references
        dangling_refs = s.run(
            """
            MATCH (src:Document)-[:REFERENCES]->(target)
            WHERE NOT (target:Document)
            RETURN count(target) AS cnt
            """
        ).single()["cnt"]

        # Constraint coverage
        cov = s.run(
            """
            MATCH (sec:Section)
            WITH count(sec) AS total
            MATCH (sec2:Section)-[:HAS_CONSTRAINT]->()
            WITH total, count(DISTINCT sec2) AS covered
            RETURN total, covered,
                   round(100.0 * covered / total, 1) AS pct
            """
        ).single()
        constraint_pct = dict(cov)["pct"] if cov else 0.0

        # Conflicts
        conflicts_cnt = s.run(
            "MATCH ()-[:CONFLICTS_WITH]->() RETURN count(*) AS cnt"
        ).single()["cnt"]

        # Recent 7-day node growth
        growth = s.run(
            """
            MATCH (n:Section)
            WHERE n.created_at >= toString(date() - duration('P7D'))
            RETURN count(n) AS cnt
            """
        ).single()["cnt"]

        # Ingest queue (pending tasks in Redis via Celery — approximated)
        ingest_queue_len = 0
        try:
            import redis as _redis
            from ...core.config import settings
            r = _redis.from_url(settings.REDIS_URL, decode_responses=True)
            ingest_queue_len = r.llen("celery") or 0
        except Exception:
            pass

    score = 100
    if isolated > 50:
        score -= 20
    if dangling_refs > 10:
        score -= 15
    if constraint_pct < 30:
        score -= 15
    if conflicts_cnt > 5:
        score -= 10

    return {
        "health_score": max(0, score),
        "isolated_nodes": isolated,
        "dangling_references": dangling_refs,
        "constraint_coverage_pct": constraint_pct,
        "conflict_count": conflicts_cnt,
        "recent_7d_node_growth": growth,
        "ingest_queue_length": ingest_queue_len,
    }
