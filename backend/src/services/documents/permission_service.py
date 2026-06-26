"""
Document-level permission checks.

visibility rules:
  "public"     — any authenticated user can read
  "department" — only users in the same department as the document
  "private"    — only the owner or an admin
"""
from __future__ import annotations

import logging
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Document, User

logger = logging.getLogger(__name__)


class DocumentPermissionService:
    # ------------------------------------------------------------------
    # Single-document check
    # ------------------------------------------------------------------

    async def can_read(
        self,
        db: AsyncSession,
        document: Document,
        user: User,
    ) -> bool:
        """Return True if *user* is allowed to read *document*."""
        if user.is_admin or user.is_platform_admin:
            return True

        vis = document.visibility

        if vis == "public":
            return True

        if vis == "private":
            return document.owner_id == user.id

        if vis == "department":
            return document.department == user.department

        # Unknown visibility value — deny by default.
        logger.warning("unknown visibility %r for doc %s", vis, document.doc_id)
        return False

    # ------------------------------------------------------------------
    # Bulk filter for list queries
    # ------------------------------------------------------------------

    async def filter_readable(
        self,
        db: AsyncSession,
        query,
        user: User,
    ):
        """Apply a WHERE clause that limits results to documents readable by *user*.

        Readable when any of:
          - visibility = 'public'
          - owner_id   = user.id
          - visibility = 'department' AND department = user.department
          - user is admin / platform admin (no filter added)
        """
        if user.is_admin or user.is_platform_admin:
            return query

        return query.where(
            or_(
                Document.visibility == "public",
                Document.owner_id == user.id,
                and_(
                    Document.visibility == "department",
                    Document.department == user.department,
                ),
            )
        )

    # ------------------------------------------------------------------
    # Ownership mutation
    # ------------------------------------------------------------------

    async def set_owner(
        self,
        db: AsyncSession,
        document_id: str,
        user_id: str,
    ) -> None:
        """Set owner_id on the Document permission row.

        Creates the row with default visibility='public' if absent.
        """
        result = await db.execute(
            select(Document).where(Document.doc_id == document_id)
        )
        doc = result.scalar_one_or_none()

        if doc is None:
            doc = Document(doc_id=document_id, owner_id=user_id)
            db.add(doc)
        else:
            doc.owner_id = user_id

        await db.commit()
