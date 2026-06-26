"""
Cursor-based pagination helpers for document list endpoints.

Cursor is an opaque base64-encoded token encoding (created_at, doc_id).
Encoding format (inside base64): "<iso8601_created_at>|<doc_id>"
"""
from __future__ import annotations

import base64
import json as _json
from datetime import datetime, timezone
from typing import Optional


def encode_cursor(created_at: datetime, doc_id: str) -> str:
    """Return an opaque pagination cursor for the given position."""
    ts = created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
    return base64.urlsafe_b64encode(f"{ts}|{doc_id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Decode a cursor; raises ValueError on bad input."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, doc_id = raw.split("|", 1)
        return datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc), doc_id
    except Exception as exc:
        raise ValueError(f"invalid cursor: {exc}") from exc


def apply_cursor(query, cursor: Optional[str], created_at_col, id_col):
    """Add a keyset WHERE clause to a SQLAlchemy query.

    Seeks past (created_at, id) encoded in the cursor.
    Returns the query unchanged when cursor is None.
    """
    if cursor is None:
        return query
    ts, doc_id = decode_cursor(cursor)
    from sqlalchemy import or_, and_
    return query.where(
        or_(
            created_at_col > ts,
            and_(created_at_col == ts, id_col > doc_id),
        )
    )


# ---------------------------------------------------------------------------
# Neo4j list-documents query (extracted from the router to keep it slim)
# ---------------------------------------------------------------------------

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

_BASE_WHERE = """
    WHERE d.title IS NOT NULL
    AND (
        $q = ''
        OR toLower(d.name)  CONTAINS toLower($q)
        OR toLower(d.title) CONTAINS toLower($q)
    )
"""

_DOC_RETURN = """
    RETURN d.name        AS doc_id,
           d.title       AS title,
           d.version     AS version,
           d.issue_date  AS issue_date,
           size([(d)-[:HAS_SECTION]->(s) | s]) AS section_count,
           size([(d)-[:HAS_IMAGE]->(i:Image) | i]) AS image_count,
           size([(d)-[:HAS_IMAGE]->(i:Image)
                 WHERE i.analysis_level IN ['full', 'basic'] | i]) AS analyzed_image_count
"""


def _img_status(img: int, analyzed: int) -> str:
    if img == 0:
        return "none"
    return "analyzed" if analyzed >= img else ("partial" if analyzed > 0 else "pending")


async def _query_documents_neo4j(
    driver,
    q: str,
    page: int,
    per_page: int,
    cursor: Optional[str],
    limit: int,
) -> dict:
    use_cursor = cursor is not None
    cursor_doc_id: Optional[str] = None
    if use_cursor:
        _, cursor_doc_id = decode_cursor(cursor)  # ValueError propagates → caller 400s

    page_size = limit if use_cursor else per_page

    try:
        from ...core.cache import get_redis
        _rc = get_redis() if not use_cursor else None
    except Exception:
        _rc = None

    cache_key = f"docs:{page}:{per_page}:{q}" if not use_cursor else None
    if _rc and cache_key:
        try:
            cached = _rc.get(cache_key)
            if cached:
                return _json.loads(cached)
        except Exception:
            pass

    cursor_clause = f"AND d.name > $cursor_doc_id" if (use_cursor and cursor_doc_id) else ""
    cypher_params: dict = {"q": q}

    if use_cursor:
        cypher_params["limit"] = page_size + 1
        if cursor_doc_id:
            cypher_params["cursor_doc_id"] = cursor_doc_id
        skip_clause, limit_expr = "", "$limit"
    else:
        cypher_params.update({"skip": (page - 1) * per_page, "per_page": page_size})
        skip_clause, limit_expr = "SKIP $skip", "$per_page"

    with driver.session() as session:
        total: Optional[int] = None
        if not use_cursor:
            r = session.run(f"MATCH (d:Document) {_BASE_WHERE} RETURN count(d) AS total", q=q)
            total = r.single()["total"]

        result = session.run(
            f"MATCH (d:Document) {_BASE_WHERE} {cursor_clause}"
            f"{_DOC_RETURN} ORDER BY d.name {skip_clause} LIMIT {limit_expr}",
            **cypher_params,
        )
        rows = []
        for r in result:
            row = dict(r)
            row["analysis_status"] = _img_status(row.get("image_count", 0), row.get("analyzed_image_count", 0))
            rows.append(row)

    next_cursor: Optional[str] = None
    if use_cursor:
        has_more = len(rows) > page_size
        documents = rows[:page_size]
        if has_more and documents:
            next_cursor = encode_cursor(_EPOCH, documents[-1]["doc_id"])
        out: dict = {"data": documents, "next_cursor": next_cursor, "limit": page_size}
    else:
        assert total is not None
        out = {"data": rows, "total": total, "page": page, "per_page": per_page,
               "pages": (total + per_page - 1) // per_page}

    if _rc and cache_key:
        try:
            _rc.setex(cache_key, 30, _json.dumps(out, default=str))
        except Exception:
            pass
    return out
