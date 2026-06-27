"""
Active Directory organizational sync.

Pulls department tree from AD and updates the local user table's
`department` and `display_name` fields. Run on schedule (e.g., nightly Celery task).

Usage:
    python -m backend.src.services.auth.ad_sync
    # or via Celery:
    from backend.src.services.auth.ad_sync import sync_org_tree
    sync_org_tree.delay()

Environment:
    LDAP_SERVER     AD hostname / IP
    LDAP_BASE_DN    e.g. DC=corp,DC=comac,DC=cc
    LDAP_BIND_DN    service account DN
    LDAP_BIND_PW    service account password

Requires:
    pip install ldap3 asyncpg
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)

LDAP_SERVER  = os.getenv("LDAP_SERVER", "ldap://corp.comac.cc")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "DC=corp,DC=comac,DC=cc")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "")
LDAP_BIND_PW = os.getenv("LDAP_BIND_PW", "")
DB_URL       = os.getenv("DATABASE_URL", "")


@dataclass
class ADUser:
    sam_account: str   # sAMAccountName (工号)
    email:       str
    display_name: str
    department:  str
    manager_dn:  str


def _fetch_ad_users() -> list[ADUser]:
    """Pull all enabled users and their department attributes from AD."""
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
    except ImportError:
        raise RuntimeError("pip install ldap3")

    server = Server(LDAP_SERVER, get_info=ALL)
    conn   = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PW, auto_bind=True)

    conn.search(
        search_base=LDAP_BASE_DN,
        search_filter="(&(objectClass=person)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))",
        search_scope=SUBTREE,
        attributes=["sAMAccountName", "mail", "displayName", "department", "manager"],
    )

    users = []
    for entry in conn.entries:
        users.append(ADUser(
            sam_account  = str(entry.sAMAccountName or ""),
            email        = str(entry.mail or ""),
            display_name = str(entry.displayName or ""),
            department   = str(entry.department or ""),
            manager_dn   = str(entry.manager or ""),
        ))
    conn.unbind()
    log.info("Fetched %d users from AD", len(users))
    return users


def _upsert_users(users: list[ADUser]) -> int:
    """Update department + display_name in local users table."""
    try:
        import asyncpg
        import asyncio
    except ImportError:
        raise RuntimeError("pip install asyncpg")

    async def _run() -> int:
        conn = await asyncpg.connect(DB_URL.replace("postgresql+asyncpg://", "postgresql://"))
        updated = 0
        for u in users:
            result = await conn.execute(
                """
                UPDATE users
                SET department   = $1,
                    display_name = $2,
                    updated_at   = NOW()
                WHERE email = $3 OR username = $4
                """,
                u.department, u.display_name, u.email, u.sam_account,
            )
            if result.split()[-1] != "0":
                updated += 1
        await conn.close()
        return updated

    return asyncio.run(_run())


def _fetch_dept_tree() -> list[dict]:
    """Return department hierarchy as a flat list with parent references."""
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
    except ImportError:
        raise RuntimeError("pip install ldap3")

    server = Server(LDAP_SERVER, get_info=ALL)
    conn   = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PW, auto_bind=True)
    conn.search(
        search_base=LDAP_BASE_DN,
        search_filter="(objectClass=organizationalUnit)",
        search_scope=SUBTREE,
        attributes=["ou", "description"],
    )
    tree = [
        {"dn": str(e.entry_dn), "name": str(e.ou or ""), "desc": str(e.description or "")}
        for e in conn.entries
    ]
    conn.unbind()
    return tree


def sync_org_tree(dry_run: bool = False) -> dict:
    """
    Full sync: pull users from AD and update local DB.
    Returns {"users_fetched": N, "users_updated": M}.
    """
    users = _fetch_ad_users()
    if dry_run:
        log.info("[dry-run] Would update %d users", len(users))
        return {"users_fetched": len(users), "users_updated": 0}
    updated = _upsert_users(users)
    log.info("AD sync complete: %d fetched, %d updated", len(users), updated)
    return {"users_fetched": len(users), "users_updated": updated}


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = sync_org_tree(dry_run=args.dry_run)
    print(result)
