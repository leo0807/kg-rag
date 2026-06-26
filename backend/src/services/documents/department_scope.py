"""
Department-based query scope helpers.

Admins see all documents; regular users see their own department plus
documents with visibility='public'.
"""
from __future__ import annotations

from sqlalchemy import or_

from ...db.models import Document, User


class DepartmentScope:
    def get_accessible_departments(self, user: User) -> list[str]:
        """Return the list of department names the user may access.

        Admins: empty list signals "all departments" (caller treats [] as unrestricted).
        Regular users: [user.department] — their own department only.
        """
        if user.is_admin or user.is_platform_admin:
            return []  # sentinel: no restriction
        return [user.department] if user.department else []

    def apply_department_filter(self, query, user: User, department_col):
        """Add a department visibility filter to *query*.

        Admins: no filter applied (see all).
        Regular users: rows where department_col matches the user's department
                       OR the row has visibility='public'.

        *department_col* is a SQLAlchemy column expression, e.g. Document.department.
        """
        if user.is_admin or user.is_platform_admin:
            return query

        return query.where(
            or_(
                Document.visibility == "public",
                department_col == user.department,
            )
        )
