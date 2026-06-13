#!/usr/bin/env python3
"""
Standalone schema-sync runner.

Usage (inside backend container or with correct env):
  DATABASE_URL=postgresql+asyncpg://... python scripts/schema-sync.py

Or rely on backend/.env:
  cd /path/to/kg-rag && python scripts/schema-sync.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Allow imports from backend/src
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Load .env if DATABASE_URL not already set
if "DATABASE_URL" not in os.environ:
    env_file = ROOT / "backend" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    sys.exit("ERROR: DATABASE_URL not set. Export it or add to backend/.env")

# Ensure async driver is specified
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)


async def main() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    # Patch settings so model imports don't crash on missing env vars
    os.environ.setdefault("NEO4J_URI",      "bolt://localhost:7687")
    os.environ.setdefault("NEO4J_USER",     "neo4j")
    os.environ.setdefault("NEO4J_PASSWORD", "password")
    os.environ.setdefault("MILVUS_HOST",    "localhost")
    os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
    os.environ.setdefault("SECRET_KEY",     "dev-secret")
    os.environ.setdefault("DATABASE_URL",   DATABASE_URL)

    engine = create_async_engine(DATABASE_URL, echo=False)

    from src.db.schema_sync import sync_schema, ensure_default_tenant

    print("=" * 60)
    print("KG-RAG Schema Sync")
    print("=" * 60)

    async with engine.begin() as conn:
        print("\n[1/2] Syncing columns …")
        changes = await sync_schema(conn)
        if changes:
            print(f"\n  Fixed {len(changes)} column(s):")
            for c in changes:
                print(f"    + {c}")
        else:
            print("  No missing columns found.")

        print("\n[2/2] Ensuring default tenant …")
        tid = await ensure_default_tenant(conn)
        print(f"  Default tenant id: {tid}")

    await engine.dispose()
    print("\n✓ Schema sync complete.")


if __name__ == "__main__":
    asyncio.run(main())
