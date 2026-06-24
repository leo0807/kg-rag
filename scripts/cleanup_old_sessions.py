#!/usr/bin/env python3
"""
cleanup_old_sessions.py — Delete conversation sessions older than N days.

Default: dry-run mode (no actual deletion).

Usage:
    python scripts/cleanup_old_sessions.py --days 30 --dry-run
    python scripts/cleanup_old_sessions.py --days 90
    python scripts/cleanup_old_sessions.py --days 30 --database-url postgresql://...
"""
import argparse
import os
import sys
from datetime import datetime, timezone, timedelta


def get_engine(database_url: str):
    from sqlalchemy import create_engine
    return create_engine(database_url)


def count_old_sessions(conn, cutoff: datetime) -> int:
    from sqlalchemy import text
    result = conn.execute(
        text("SELECT COUNT(*) FROM conversations WHERE updated_at < :cutoff"),
        {"cutoff": cutoff}
    )
    return result.scalar() or 0


def fetch_old_session_ids(conn, cutoff: datetime, batch_size: int) -> list:
    from sqlalchemy import text
    result = conn.execute(
        text("SELECT id FROM conversations WHERE updated_at < :cutoff LIMIT :limit"),
        {"cutoff": cutoff, "limit": batch_size}
    )
    return [row[0] for row in result.fetchall()]


def delete_sessions(conn, ids: list) -> int:
    if not ids:
        return 0
    from sqlalchemy import text
    placeholders = ",".join(f":id{i}" for i in range(len(ids)))
    params = {f"id{i}": v for i, v in enumerate(ids)}
    result = conn.execute(text(f"DELETE FROM conversations WHERE id IN ({placeholders})"), params)
    return result.rowcount


def main():
    parser = argparse.ArgumentParser(description="Clean up old conversation sessions")
    parser.add_argument("--days", type=int, default=30, help="Delete sessions older than N days (default: 30)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview only, no deletion (default: enabled)")
    parser.add_argument("--execute", action="store_true",
                        help="Actually delete sessions (overrides --dry-run)")
    parser.add_argument("--database-url", help="SQLAlchemy database URL")
    parser.add_argument("--batch-size", type=int, default=500, help="Delete in batches (default: 500)")
    args = parser.parse_args()

    dry_run = not args.execute

    database_url = args.database_url or os.getenv(
        "DATABASE_URL", "postgresql://postgres:password@localhost:5432/kgrag"
    )

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=args.days)
    print(f"Sessions older than: {cutoff.date()} ({args.days} days)")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")

    try:
        engine = get_engine(database_url)
    except Exception as e:
        print(f"ERROR: Cannot create DB engine: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with engine.connect() as conn:
            total = count_old_sessions(conn, cutoff)
            print(f"Found {total} sessions to delete")

            if total == 0:
                print("Nothing to clean up.")
                return

            if dry_run:
                sample_ids = fetch_old_session_ids(conn, cutoff, batch_size=5)
                print(f"Sample IDs that would be deleted: {sample_ids}")
                print("[dry-run] No changes made. Use --execute to delete.")
                return

            deleted = 0
            while True:
                ids = fetch_old_session_ids(conn, cutoff, args.batch_size)
                if not ids:
                    break
                n = delete_sessions(conn, ids)
                deleted += n
                print(f"  Deleted batch of {n} (total so far: {deleted})")
            conn.commit()
            print(f"\nDone. Deleted {deleted} sessions.")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
