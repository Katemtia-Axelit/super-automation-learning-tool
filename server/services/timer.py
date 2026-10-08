"""server.services.timer - business logic for timer domain.

Owns:
- start/complete/active/pause/resume workflows on `timer_sessions`
- `paused_seconds` accumulation semantics (P3 bug fix)

Layered on top of `server.repositories.timer_repo` (pure SQL).
No Flask imports — usable from CLI or BP.

Migration source: backend_api.py L3054-3181.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from server.repositories import timer_repo


# Custom error so BP can map to 400/404 cleanly.
class TimerError(Exception):
    """Domain error carrying an HTTP status hint and a user-facing message."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# =============================================================================
# Start
# =============================================================================

def start(conn, task_id, planned_minutes: int = 30) -> Dict[str, Any]:
    """Start a new timer session. Reject re-entry on the same task.

    Mirrors backend_api.py L3054-3075 (api_timer_start).
    """
    if not task_id:
        raise TimerError("task_id required", status=400)
    existing = timer_repo.find_active_for_task(conn, task_id)
    if existing:
        raise TimerError("该任务已有进行中的计时", status=400)

    now_iso = datetime.now().isoformat()
    sid = timer_repo.create_session(conn, task_id, now_iso, planned_minutes)
    return {
        "session_id": sid,
        "task_id": task_id,
        "started_at": now_iso,
        "planned_minutes": planned_minutes,
    }


# =============================================================================
# Complete
# =============================================================================

def complete(
    conn,
    session_id,
    actual_minutes=None,
    result: str = "completed",
    reason: str = "",
) -> Dict[str, Any]:
    """Mark a timer session ended. Accepts running or paused (P3-Bug-B).

    Mirrors backend_api.py L3077-3099 (api_timer_complete).
    """
    if not session_id:
        raise TimerError("session_id required", status=400)
    now_iso = datetime.now().isoformat()
    ok = timer_repo.mark_completed(conn, session_id, now_iso, actual_minutes, result, reason)
    if not ok:
        raise TimerError("计时会话未找到或已结束", status=404)
    return {"ended": True, "session_id": session_id, "result": result}


# =============================================================================
# Active
# =============================================================================

def active(conn) -> Optional[Dict[str, Any]]:
    """Return the latest active session (running or paused) joined with task name.

    Adds `is_paused` boolean derived from `status` (P3 bug note: resume resets
    paused counts, so trust `status` field over `paused_seconds` for pause UI).

    Mirrors backend_api.py L3101-3118 (api_timer_active).
    """
    row = timer_repo.get_active_session(conn)
    if row is None:
        return None
    row["is_paused"] = (row.get("status") == "paused")
    return row


# =============================================================================
# Pause
# =============================================================================

def pause(conn) -> Dict[str, Any]:
    """Pause the currently-running timer, accumulating paused_seconds.

    Behavior mirrors backend_api.py L3120-3153 (api_timer_pause) EXACTLY:
    - Locate the latest running session.
    - Compute the increment = existing paused_seconds + elapsed since last started_at.
    - UPDATE paused_seconds = increment, started_at = NOW, status = "paused".

    Returns the post-pause state of the session for the BP to echo to the client.
    """
    row = timer_repo.find_running_session(conn)
    if row is None:
        raise TimerError("没有活动中的计时器", status=404)

    session_id = row["id"]
    started_at_iso = row["started_at"]
    paused_secs = row["paused_seconds"] or 0

    # Compute elapsed since last started_at (resume or initial start).
    last_started = datetime.fromisoformat(started_at_iso)
    elapsed_since_start = (datetime.now() - last_started).total_seconds()
    new_paused = int(paused_secs + elapsed_since_start)

    now_iso = datetime.now().isoformat()
    ok = timer_repo.accumulate_pause(conn, session_id, new_paused, now_iso)
    if not ok:
        raise TimerError("暂停失败", status=500)

    return {
        "session_id": session_id,
        "is_paused": True,
        "paused_seconds": new_paused,
        "started_at": now_iso,
    }


# =============================================================================
# Resume
# =============================================================================

def resume(conn) -> Dict[str, Any]:
    """Resume a paused timer. Sets started_at to NOW and status='running'.

    Mirrors backend_api.py L3155-3181 (api_timer_resume).
    """
    row = timer_repo.find_paused_session(conn)
    if row is None:
        raise TimerError("没有暂停中的计时器", status=404)

    session_id = row["id"]
    now_iso = datetime.now().isoformat()
    ok = timer_repo.mark_resumed(conn, session_id, now_iso)
    if not ok:
        raise TimerError("恢复失败", status=500)

    return {
        "session_id": session_id,
        "is_paused": False,
        "started_at": now_iso,
    }


__all__ = [
    "TimerError",
    "start",
    "complete",
    "active",
    "pause",
    "resume",
]