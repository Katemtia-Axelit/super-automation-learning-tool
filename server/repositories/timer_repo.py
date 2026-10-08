"""server.repositories.timer_repo - timer_sessions (Phase 2).

Pure SQL functions for the `timer_sessions` table.
Migrated from backend_api.py timer domain (L3054-3181).

Conventions:
- All functions take a `conn` argument (caller manages connection lifecycle).
- Return rows as `dict` (sqlite3.Row converted by caller) or scalar.
- No Flask imports — pure data layer.
- `paused_seconds` semantics (P3 bug fix): accumulated via atomic UPDATE
  `paused_seconds = paused_seconds + ?`. See `accumulate_pause`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


# =============================================================================
# Timer session lookup helpers
# =============================================================================

def get_active_session(conn) -> Optional[Dict[str, Any]]:
    """Return the latest running or paused session joined with task name, or None.

    Joins `timer_sessions` with `tasks` to attach `task_name` for the BP layer.
    Mirrors backend_api.py L3106-3109 (api_timer_active).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ts.id, ts.task_id, ts.started_at, ts.planned_minutes,
               ts.paused_seconds, ts.status, t.name as task_name
        FROM timer_sessions ts JOIN tasks t ON ts.task_id = t.id
        WHERE ts.status IN ('running', 'paused')
        ORDER BY ts.started_at DESC LIMIT 1
        """
    )
    row = cur.fetchone()
    return dict(row) if row else None


def find_running_session(conn) -> Optional[Dict[str, Any]]:
    """Return the latest strictly-running session, or None.

    Mirrors backend_api.py L3128-3129 (api_timer_pause lookup).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, started_at, paused_seconds
        FROM timer_sessions
        WHERE status = "running"
        ORDER BY started_at DESC LIMIT 1
        """
    )
    row = cur.fetchone()
    return dict(row) if row else None


def find_paused_session(conn) -> Optional[Dict[str, Any]]:
    """Return the latest strictly-paused session, or None.

    Mirrors backend_api.py L3163-3164 (api_timer_resume lookup).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, paused_seconds
        FROM timer_sessions
        WHERE status = "paused"
        ORDER BY started_at DESC LIMIT 1
        """
    )
    row = cur.fetchone()
    return dict(row) if row else None


def find_active_for_task(conn, task_id: int) -> Optional[Dict[str, Any]]:
    """Return running session for a specific task (re-entry guard), or None.

    Mirrors backend_api.py L3066 (api_timer_start re-entry check).
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM timer_sessions WHERE task_id=? AND status='running'",
        (task_id,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


# =============================================================================
# Timer session mutations
# =============================================================================

def create_session(conn, task_id: int, started_at_iso: str, planned_minutes: int) -> int:
    """INSERT a new running timer_sessions row. Return session id.

    Caller is responsible for the re-entry check (use `find_active_for_task`).
    """
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO timer_sessions (task_id, started_at, planned_minutes, status) "
        "VALUES (?,?,?,?)",
        (task_id, started_at_iso, planned_minutes, "running"),
    )
    conn.commit()
    return cur.lastrowid


def mark_completed(
    conn,
    session_id: int,
    ended_at_iso: str,
    actual_minutes,
    result: str,
    reason: str,
) -> bool:
    """UPDATE session to ended. Accepts running OR paused sessions (P3-Bug-B).

    Returns True if a row was updated.
    """
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE timer_sessions
        SET ended_at=?, actual_minutes=?, status="ended", result=?, reason=?
        WHERE id=? AND status IN ("running", "paused")
        """,
        (ended_at_iso, actual_minutes, result, reason, session_id),
    )
    conn.commit()
    return cur.rowcount > 0


def accumulate_pause(
    conn, session_id: int, paused_seconds_increment: int, new_started_at_iso: str
) -> bool:
    """Atomic pause: increment paused_seconds + set new started_at + status=paused.

    Mirrors backend_api.py L3141-3144 (api_timer_pause UPDATE).
    The caller computes `paused_seconds_increment` as
    `(existing_paused_seconds + elapsed_since_last_started_at)`.
    """
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE timer_sessions
        SET paused_seconds=?, started_at=?, status="paused"
        WHERE id=?
        """,
        (paused_seconds_increment, new_started_at_iso, session_id),
    )
    conn.commit()
    return cur.rowcount > 0


def mark_resumed(conn, session_id: int, new_started_at_iso: str) -> bool:
    """Mark a paused session as running with new started_at.

    Mirrors backend_api.py L3170-3173 (api_timer_resume UPDATE).
    """
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE timer_sessions
        SET started_at=?, status="running"
        WHERE id=?
        """,
        (new_started_at_iso, session_id),
    )
    conn.commit()
    return cur.rowcount > 0


__all__ = [
    "get_active_session",
    "find_running_session",
    "find_paused_session",
    "find_active_for_task",
    "create_session",
    "mark_completed",
    "accumulate_pause",
    "mark_resumed",
]