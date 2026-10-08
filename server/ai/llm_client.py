"""server.ai.llm_client — Phase 1 placeholder.

Phase 2 will own the actual LLM HTTP calls (openai / claude) with
timeouts, retries, and JSON-mode wrappers.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def call_llm(messages: list, *, model: Optional[str] = None, **kwargs: Any) -> str:
    """Phase 1 thin wrapper around backend_api.call_llm."""
    from server.backend_api import call_llm as _impl
    return _impl(messages, model=model, **kwargs)


__all__ = ["call_llm"]