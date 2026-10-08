"""server.repositories.task_repo — task CRUD (Phase 1 stub).

Phase 1 keeps the actual SQL inside `backend_api.py`. This module exists
as a forward anchor and re-exports the four most-used entry points so
blueprints can `from server.repositories import task_repo as repo`.

Phase 2 will move all the SQL into here and have blueprints import only
`repo` (no direct sqlite3 references).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_all_tasks(include_completed: bool = False, unlocked_only: bool = False) -> List[Any]:
    """Phase-1 passthrough to backend_api.get_all_tasks."""
    from server.backend_api import get_all_tasks as _impl
    return _impl(include_completed=include_completed, unlocked_only=unlocked_only)


def get_task_by_id(task_id: int) -> Optional[Any]:
    from server.backend_api import get_task_by_id as _impl
    return _impl(task_id)


def add_task(task: Any) -> int:
    from server.backend_api import add_task as _impl
    return _impl(task)


def update_task(task: Any) -> None:
    from server.backend_api import update_task as _impl
    return _impl(task)


def delete_task(task_id: int) -> None:
    from server.backend_api import delete_task as _impl
    return _impl(task_id)


def get_task_dependents(task_id: int) -> List[Dict[str, Any]]:
    from server.extensions import get_db_connection
    conn = get_db_connection()
    try:
        from server.backend_api import get_task_dependents as _impl
        return _impl(conn, task_id)
    finally:
        conn.close()


def get_available_for_gacha() -> List[Dict[str, Any]]:
    from server.backend_api import get_available_tasks_for_gacha as _impl
    return _impl()


def update_draw_count(task_id: int) -> None:
    from server.backend_api import update_draw_count as _impl
    return _impl(task_id)


def get_discard_pile() -> List[Any]:
    from server.backend_api import get_discard_pile_tasks as _impl
    return _impl()


def move_to_discard(task_id: int) -> None:
    from server.backend_api import move_task_to_discard_pile as _impl
    return _impl(task_id)


def move_to_gacha_pile(task_id: int) -> None:
    from server.backend_api import move_task_to_gacha_pile as _impl
    return _impl(task_id)