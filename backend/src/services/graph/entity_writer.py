"""Compatibility facade for graph entity persistence helpers."""

from .entity_graph_reset import (
    cleanup_stale_document_nodes,
    reset_document_entity_graph,
    reset_document_tables,
    reset_document_text_constraints,
)
from .entity_graph_write import (
    link_image_tools,
    write_constraints,
    write_drawing_constraints,
    write_entities,
    write_tables,
)
from .entity_writer_support import collect_section_entities as _collect_section_entities

__all__ = [
    "cleanup_stale_document_nodes",
    "reset_document_entity_graph",
    "reset_document_tables",
    "reset_document_text_constraints",
    "write_constraints",
    "write_drawing_constraints",
    "write_entities",
    "write_tables",
    "link_image_tools",
    "_collect_section_entities",
]
