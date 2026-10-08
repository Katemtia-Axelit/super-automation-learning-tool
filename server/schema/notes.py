"""server.schema.notes — knowledge-base index metadata.

Currently the knowledge base lives in `src/notes/` (Obsidian vault) and is
read at request time. There is no SQLite persistence for notes in
`backend_api.py`. This module exists as a forward-compatible anchor for
Phase 2/3 when `notes_categories` / `notes_files` may be added.

`notes_directory` and `vault_path` are read from config; if the directory
is missing, `ensure_schema` is a no-op (no DB tables to create).
"""
from __future__ import annotations

import os


def ensure_schema(conn) -> None:  # pragma: no cover
    """No-op today; placeholder for future notes index tables."""
    return None


__all__ = ["ensure_schema"]