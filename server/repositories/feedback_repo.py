"""server.repositories.feedback_repo - task feedback persistence (Phase 2).

Pure SQL functions for `task_completion_feedback` and `task_feedback_events` tables.

Migrated from backend_api.py:
- `insert_task_feedback_event` (L786-810) → `insert_event`
- `api_list_task_feedback` (L2394-2413) → `list_events`
- `api_task_feedback` (L2338-2362) → `insert_completion_feedback`

Conventions:
- All functions take a `conn` argument (caller manages connection lifecycle).
- Return rows as `dict` (sqlite3.Row converted by caller).
- No Flask imports — pure data layer.
- Caller is responsible for `conn.commit()` in transactional contexts.

Tables:
- `task_feedback_events` — schema owner: `server/schema/feedback.py`. Used by
  POST/GET `/api/task-feedback`.
- `task_completion_feedback` — schema owner: NONE (Todo 11 will add). Already
  created by `_archive/06_测试脚本/rebuild_tasks.py:180-182`. Used by
  POST `/api/tasks/<id>/feedback`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


# =============================================================================
# task_completion_feedback table
# =============================================================================

def insert_completion_feedback(
    conn,
    task_id: int,
    energy_after: Optional[int],
    mood_after: Optional[str],
    timestamp: Optional[str] = None,
) -> None:
    """Insert a single row into task_completion_feedback.

    Columns: task_id, energy_after, mood_after, timestamp.
    `timestamp` defaults to `datetime.now().isoformat()` if omitted.
    """
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO task_completion_feedback "
        "(task_id, energy_after, mood_after, timestamp) VALUES (?, ?, ?, ?)",
        (task_id, energy_after, mood_after, timestamp),
    )
    conn.commit()


# =============================================================================
# task_feedback_events table
# =============================================================================

def insert_event(conn, event_data: Dict[str, Any]) -> int:
    """Insert a row into task_feedback_events and return the new row id.

    Required keys in `event_data`: task_id, event_type, reason_category.
    Optional keys: planned_minutes, actual_minutes, completion_status,
    reason_detail, note. created_at defaults to `datetime.now().isoformat()`.
    """
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO task_feedback_events "
        "(task_id, event_type, planned_minutes, actual_minutes, completion_status, "
        "reason_category, reason_detail, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_data["task_id"],
            event_data["event_type"],
            event_data.get("planned_minutes"),
            event_data.get("actual_minutes"),
            event_data.get("completion_status"),
            event_data["reason_category"],
            event_data.get("reason_detail"),
            event_data.get("note"),
            now,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_events(conn, task_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Return task_feedback_events rows, optionally filtered by task_id.

    Always ORDER BY created_at DESC. Default limit 100 (matches backend_api.py).
    """
    cur = conn.cursor()
    if task_id is not None:
        cur.execute(
            "SELECT * FROM task_feedback_events WHERE task_id=? "
            "ORDER BY created_at DESC",
            (task_id,),
        )
    else:
        cur.execute(
            "SELECT * FROM task_feedback_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    return [dict(r) for r in cur.fetchall()]


__all__ = [
    "insert_completion_feedback",
    "insert_event",
    "list_events",
]
