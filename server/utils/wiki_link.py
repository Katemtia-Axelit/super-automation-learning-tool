"""server.utils.wiki_link — Obsidian [[link]] parser.

Phase 1: passthrough (the heavy lifting is in `backend_api._resolve_md_link`
+ `_extract_links_from_content`). Phase 2 will own the parser.
"""
from __future__ import annotations

from typing import List, Tuple


def extract_links(content: str) -> List[Tuple[str, int]]:
    """Return list of (target, offset) pairs for [[...]] links."""
    from server.backend_api import _extract_links_from_content as _impl
    return _impl(content)


def resolve_md_link(target: str, current_note_path: str) -> str:
    """Resolve a [[link]] to a vault-relative path."""
    from server.backend_api import _resolve_md_link as _impl
    return _impl(target, current_note_path)