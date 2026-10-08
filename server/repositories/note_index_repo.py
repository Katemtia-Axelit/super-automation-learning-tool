"""server.repositories.note_index_repo - knowledge-base index (Phase 2).

Pure file-system helpers for the Obsidian-style vault under `notes_dir`.
Phase 1 walks the vault directly; Phase 2/3 may add a SQLite-backed index
for performance. Until then, these helpers expose the pure data layer so
that `server.services.knowledge` and `server.blueprints.knowledge_bp` do
not have to perform raw `os.listdir`/`os.walk` work themselves.

Conventions:
- Pure functions only — no Flask imports, no `current_app`.
- All functions take the vault root (`notes_dir`) explicitly so they can
  be tested or reused from CLI / scripts.
- Returned dicts use stable keys consumed by the BP layer verbatim.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List


def count_md_files_in_category(notes_dir: str, subject_dir_name: str) -> int:
    """Count `.md` files directly inside `<notes_dir>/知识点/<subject_dir_name>`.

    Mirrors backend_api.py `api_get_knowledge_categories` (L1600-1627).
    Walks one level deep only — does not recurse into sub-directories.
    """
    if not notes_dir:
        return 0
    subject_path = os.path.join(notes_dir, "知识点", subject_dir_name)
    if not os.path.isdir(subject_path):
        return 0
    return sum(1 for f in os.listdir(subject_path) if f.endswith(".md"))


def list_categories(notes_dir: str) -> List[Dict[str, Any]]:
    """Return the 5 fixed knowledge subjects with current `.md` counts.

    Mirrors backend_api.py L1596-1629 (`api_get_knowledge_categories`).
    Preserves the historical fallback counts (linear=8 / computer=6) when
    a directory is missing — this is intentional behavior, not a bug.
    """
    categories: List[Dict[str, Any]] = []

    def _entry(cid: str, cname: str, fallback: int = 0) -> Dict[str, Any]:
        count = count_md_files_in_category(notes_dir, cname)
        if count == 0 and fallback:
            count = fallback
        return {"id": cid, "name": cname, "count": count}

    categories.append(_entry("math", "高等数学"))
    categories.append(_entry("physics", "大学物理"))
    categories.append(_entry("linear", "线性代数", fallback=8))
    categories.append(_entry("electronics", "电子技术"))
    categories.append(_entry("computer", "计算机", fallback=6))
    return categories


def recent_notes() -> List[Dict[str, Any]]:
    """Return hardcoded 4 placeholder entries (P3 known issue).

    Mirrors backend_api.py L1864-1872 (`api_get_recent_knowledge`).
    Preserved verbatim so the front-end does not change behavior.
    """
    return [
        {"name": "高斯定理", "category": "大学物理"},
        {"name": "矩阵运算", "category": "线性代数"},
        {"name": "导数", "category": "高等数学"},
        {"name": "布尔代数", "category": "电子技术"},
    ]


__all__ = [
    "count_md_files_in_category",
    "list_categories",
    "recent_notes",
]