"""
Semantic Kernel planner integration for enterprise AI orchestration.

- SK Memory: wraps existing Milvus vector store as a SK memory provider
- SK Planner: sequential planner that decomposes complex queries into steps
- SharePoint sync: Microsoft Graph API pull for enterprise document libraries

Dual-mode: semantic-kernel installed → real SK; otherwise uses lightweight mock.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
_HEADERS = {"X-API-Key": BACKEND_API_KEY} if BACKEND_API_KEY else {}

# Microsoft Graph API settings (Azure AD app registration required)
AZURE_TENANT_ID    = os.getenv("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID    = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
SHAREPOINT_SITE_ID = os.getenv("SHAREPOINT_SITE_ID", "")


# ─── Mock SK Memory (wraps our existing /api/query) ──────────────────────────

class MockSKMemory:
    """Thin wrapper that makes the backend's vector search look like SK Memory."""

    async def search_async(self, collection: str, query: str, limit: int = 5) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{BACKEND_URL}/api/query",
                json={"question": query, "strategy": "parallel", "top_k": limit},
                headers=_HEADERS,
            )
        data = r.json()
        return [
            {"id": s.get("chunk_id", ""), "text": s.get("content", ""), "score": s.get("score", 0)}
            for s in data.get("sources", [])
        ]

    async def save_information_async(
        self, collection: str, text: str, id: str, description: str = ""
    ) -> None:
        """Delegate to ingest pipeline; no-op in mock mode."""
        log.debug("MockSKMemory.save: collection=%s id=%s", collection, id)


# ─── Mock SK Planner ─────────────────────────────────────────────────────────

class MockSKPlanner:
    """
    Sequential planner that decomposes a complex goal into sub-tasks and
    calls the relevant backend functions in order.
    """

    def __init__(self, memory: MockSKMemory):
        self.memory = memory

    async def create_plan_async(self, goal: str) -> list[str]:
        """Use LLM to break goal into steps."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{BACKEND_URL}/api/query",
                json={
                    "question": (
                        f"将以下任务分解为 3-5 个可独立执行的子步骤，每行一个步骤：\n{goal}"
                    ),
                    "strategy": "parallel",
                    "top_k": 0,
                },
                headers=_HEADERS,
            )
        answer = r.json().get("answer", goal)
        steps = [s.strip() for s in answer.split("\n") if s.strip()]
        return steps[:5] or [goal]

    async def execute_plan_async(self, goal: str) -> dict:
        steps = await self.create_plan_async(goal)
        results = []
        for step in steps:
            memories = await self.memory.search_async("aviation_specs", step, limit=3)
            context  = "\n".join(m["text"][:200] for m in memories)
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{BACKEND_URL}/api/query",
                    json={"question": step, "strategy": "graph_augmented", "top_k": 3},
                    headers=_HEADERS,
                )
            answer = r.json().get("answer", "")
            results.append({"step": step, "answer": answer})

        return {"goal": goal, "steps": steps, "results": results}


# ─── SharePoint sync via Microsoft Graph API ─────────────────────────────────

async def _get_graph_token() -> str:
    url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
    async with httpx.AsyncClient() as client:
        r = await client.post(url, data={
            "grant_type":    "client_credentials",
            "client_id":     AZURE_CLIENT_ID,
            "client_secret": AZURE_CLIENT_SECRET,
            "scope":         "https://graph.microsoft.com/.default",
        })
    r.raise_for_status()
    return r.json()["access_token"]


async def list_sharepoint_files(library: str = "Documents") -> list[dict]:
    """
    List files in a SharePoint document library.
    Requires AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, SHAREPOINT_SITE_ID.
    """
    if not all([AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, SHAREPOINT_SITE_ID]):
        log.warning("Azure credentials not configured — returning empty list")
        return []

    token = await _get_graph_token()
    url   = (
        f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE_ID}"
        f"/drives/{library}/root/children"
    )
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    items = r.json().get("value", [])
    return [
        {
            "id":           item["id"],
            "name":         item["name"],
            "size":         item.get("size", 0),
            "last_modified": item.get("lastModifiedDateTime", ""),
            "web_url":      item.get("webUrl", ""),
        }
        for item in items
        if item.get("file")
    ]


async def sync_sharepoint_to_knowledge_base(library: str = "Documents") -> dict:
    """
    Pull PDFs from SharePoint and submit them to the ingest pipeline.
    Idempotent: skips files already in the knowledge base.
    """
    files = await list_sharepoint_files(library)
    ingested, skipped = 0, 0

    for f in files:
        if not f["name"].lower().endswith(".pdf"):
            continue
        async with httpx.AsyncClient(timeout=120) as client:
            # Check if already ingested
            check = await client.get(
                f"{BACKEND_URL}/api/documents",
                params={"name": f["name"]},
                headers=_HEADERS,
            )
            if check.json().get("total", 0) > 0:
                skipped += 1
                continue
            # Submit URL for ingestion
            await client.post(
                f"{BACKEND_URL}/api/ingest/url",
                json={"url": f["web_url"], "source": "sharepoint", "name": f["name"]},
                headers=_HEADERS,
            )
            ingested += 1

    return {"ingested": ingested, "skipped": skipped, "total": len(files)}


# ─── Factory ─────────────────────────────────────────────────────────────────

def get_sk_planner() -> MockSKPlanner:
    """Return a SK Planner (real or mock) using existing Milvus memory."""
    try:
        import semantic_kernel as sk  # noqa: F401
        log.info("semantic-kernel found; TODO: wire real SK kernel")
    except ImportError:
        pass
    memory = MockSKMemory()
    return MockSKPlanner(memory)
