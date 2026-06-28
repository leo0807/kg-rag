#!/usr/bin/env python3
"""
PLM Document Sync Script.

Periodically pulls "published" documents from PLM systems (Teamcenter/Windchill/ENOVIA)
and triggers incremental ingest for new or updated versions.

Usage:
    python scripts/plm_sync.py \
        --plm-type teamcenter \
        --plm-url https://plm.corp.com/api \
        --plm-token "$PLM_TOKEN" \
        --backend-url http://localhost:8000 \
        --api-key "$API_KEY" \
        --dry-run

Supports:
    --plm-type teamcenter | windchill | enovia
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


class PLMClient:
    """Thin PLM REST client (Teamcenter, Windchill, ENOVIA)."""

    def __init__(self, plm_type: str, base_url: str, token: str) -> None:
        self.plm_type = plm_type
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def list_published_documents(self, since: datetime) -> list[dict[str, Any]]:
        """Return list of published documents modified since `since`."""
        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        endpoint_map = {
            "teamcenter": "/fms/fmsrest/workspace/document?status=Published",
            "windchill": "/api/v1/documents?state=RELEASED",
            "enovia": "/api/v1/document/search?state=released",
        }
        endpoint = endpoint_map.get(self.plm_type, "/api/documents")
        try:
            with httpx.Client(base_url=self.base_url, headers=self._headers(),
                               timeout=30) as c:
                r = c.get(endpoint, params={"modified_since": since_str})
                r.raise_for_status()
                data = r.json()
                return data.get("items", data.get("documents", data.get("data", [])))
        except Exception as exc:
            log.error("PLM list_published_documents failed: %s", exc)
            return []

    def download_document(self, doc_meta: dict) -> bytes | None:
        """Download document PDF bytes."""
        download_url = doc_meta.get("download_url", doc_meta.get("url", ""))
        if not download_url:
            return None
        try:
            with httpx.Client(headers=self._headers(), timeout=120) as c:
                r = c.get(download_url)
                r.raise_for_status()
                return r.content
        except Exception as exc:
            log.error("Download failed for %s: %s", doc_meta.get("id"), exc)
            return None


class BackendClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key}

    def get_existing_docs(self) -> set[str]:
        """Return set of already-ingested doc IDs."""
        try:
            with httpx.Client(base_url=self.base_url, headers=self.headers,
                               timeout=30) as c:
                r = c.get("/api/documents", params={"per_page": 1000})
                r.raise_for_status()
                data = r.json()
                docs = data.get("documents", data)
                return {d["name"] for d in docs}
        except Exception as exc:
            log.error("Failed to list existing docs: %s", exc)
            return set()

    def ingest_document(self, doc_id: str, title: str,
                         pdf_bytes: bytes) -> bool:
        """Submit document for ingestion."""
        try:
            import io
            with httpx.Client(base_url=self.base_url, headers=self.headers,
                               timeout=300) as c:
                r = c.post(
                    "/api/ingest",
                    files={"file": (f"{doc_id}.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
                    data={"doc_id": doc_id, "title": title},
                )
                r.raise_for_status()
                return True
        except Exception as exc:
            log.error("Ingest failed for %s: %s", doc_id, exc)
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description="PLM document sync")
    parser.add_argument("--plm-type", default=os.getenv("PLM_TYPE", "teamcenter"),
                        choices=["teamcenter", "windchill", "enovia"])
    parser.add_argument("--plm-url", default=os.getenv("PLM_URL", ""))
    parser.add_argument("--plm-token", default=os.getenv("PLM_TOKEN", ""))
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.getenv("BACKEND_API_KEY", ""))
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.plm_url:
        print("Error: --plm-url required (or PLM_URL env var)", file=sys.stderr)
        sys.exit(1)

    plm = PLMClient(args.plm_type, args.plm_url, args.plm_token)
    backend = BackendClient(args.backend_url, args.api_key)

    since = datetime.utcnow() - timedelta(hours=args.lookback_hours)
    log.info("Checking PLM for documents published since %s", since.isoformat())

    published = plm.list_published_documents(since)
    log.info("Found %d published documents", len(published))

    if not published:
        print("No new documents found.")
        return

    existing = backend.get_existing_docs()
    new_docs = [d for d in published if d.get("id", d.get("name")) not in existing]
    log.info("%d new documents to ingest", len(new_docs))

    ingested = failed = 0
    for doc in new_docs:
        doc_id = doc.get("id", doc.get("name", f"doc_{ingested}"))
        title = doc.get("title", doc.get("name", doc_id))
        log.info("Processing: %s — %s", doc_id, title)

        if args.dry_run:
            print(f"  [DRY RUN] Would ingest: {doc_id} — {title}")
            continue

        pdf_bytes = plm.download_document(doc)
        if not pdf_bytes:
            log.warning("Skipping %s: download failed", doc_id)
            failed += 1
            continue

        success = backend.ingest_document(doc_id, title, pdf_bytes)
        if success:
            ingested += 1
            log.info("  ✓ Ingested: %s", doc_id)
        else:
            failed += 1

        time.sleep(1)  # rate limit

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}PLM sync complete:")
    print(f"  Total published: {len(published)}")
    print(f"  New documents: {len(new_docs)}")
    if not args.dry_run:
        print(f"  Ingested: {ingested}")
        print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
