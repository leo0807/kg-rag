"""Compatibility facade for table extraction helpers."""

from .strategies import (
    extract_all_tables,
    extract_tables_full,
    extract_tables_structured,
    is_available,
)

__all__ = [
    "extract_all_tables",
    "extract_tables_full",
    "extract_tables_structured",
    "is_available",
]
