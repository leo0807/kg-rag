"""Compatibility facade for the split LLM service modules."""

from .errors import LLMError
from .service import LLMService, get_llm_service

__all__ = ["LLMError", "LLMService", "get_llm_service"]
