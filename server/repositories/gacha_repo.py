"""server.repositories.gacha_repo — gacha persistence (Phase 1 stub).

Phase 1 doesn't persist gacha history. This module is a forward anchor;
Phase 2 may add gacha_records / task_publishes tables.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_all_tags_for_tasks(conn, task_ids: List[int]) -> Dict[int, List[str]]:
    from server.backend_api import get_all_tags_for_tasks as _impl
    return _impl(conn, task_ids)


def get_task_tags(conn, task_id: int) -> List[str]:
    from server.backend_api import get_task_tags as _impl
    return _impl(conn, task_id)