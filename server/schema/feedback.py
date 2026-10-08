"""server.schema.feedback — task_feedback_events table.

Migrates `ensure_task_feedback_events_schema()` from `backend_api.py`.

`timer_sessions` (timer) is *not* in this file — per the Plan's domain split,
it belongs to `server.schema.timer`, but Phase 1 keeps it in `backend_api.py`
under `ensure_timer_schema()` for backward compatibility with the existing
`/api/timer/*` route registrations. The split is mirrored in
`server.schema.state` (state_assessments / daily_user_state) so the dependency
graph `feedback → tasks` is satisfied.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .state import _ensure_table_columns


def ensure_schema(conn) -> None:
    """Idempotent creation of task_feedback_events + indexes."""
    cur = conn.cursor()
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS task_feedback_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            planned_minutes INTEGER,
            actual_minutes INTEGER,
            completion_status TEXT,
            reason_category TEXT NOT NULL,
            reason_detail TEXT,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
        '''
    )
    _ensure_table_columns(
        cur,
        'task_feedback_events',
        [
            ('task_id', 'INTEGER', None),
            ('event_type', 'TEXT', None),
            ('planned_minutes', 'INTEGER', None),
            ('actual_minutes', 'INTEGER', None),
            ('completion_status', 'TEXT', None),
            ('reason_category', 'TEXT', None),
            ('reason_detail', 'TEXT', None),
            ('note', 'TEXT', None),
            ('created_at', 'TEXT', 'CURRENT_TIMESTAMP'),
        ],
    )
    cur.execute('CREATE INDEX IF NOT EXISTS idx_task_feedback_task ON task_feedback_events(task_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_task_feedback_created ON task_feedback_events(created_at)')
    conn.commit()


__all__ = ["ensure_schema"]