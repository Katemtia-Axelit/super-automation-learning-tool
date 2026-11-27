"""server.schema.timer — 计时器域的 **唯一 Schema 权威**。

本模块拥有 ``timer_sessions`` 表：``/api/timer/*`` 的全部读写都落在这里
（见 ``server/repositories/timer_repo.py``）。

权威 DDL 来自 ``_archive/06_测试脚本/rebuild_tasks.py``
（历史权威）与 ``server/backend_api.py::ensure_timer_schema``
（当前真实运行契约）的并集。

``paused_seconds``
------------------
P3-Bug 修复引入的暂停持久化列：累计暂停秒数，刷新页面后可恢复。
既有库缺该列时由本模块幂等补齐。
"""

from __future__ import annotations

import sqlite3
from typing import Optional, Sequence, Tuple

#: ``timer_sessions`` 的权威 DDL。
TIMER_SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS timer_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    planned_minutes INTEGER,
    actual_minutes INTEGER,
    status TEXT DEFAULT 'running',
    result TEXT,
    reason TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
)
"""

#: 幂等补列契约。
TIMER_SESSIONS_COLUMNS: Tuple[Tuple[str, str, Optional[str]], ...] = (
    ("task_id", "INTEGER", "NULL"),
    ("started_at", "TEXT", "NULL"),
    ("ended_at", "TEXT", "NULL"),
    ("planned_minutes", "INTEGER", "NULL"),
    ("actual_minutes", "INTEGER", "NULL"),
    ("status", "TEXT", "'running'"),
    ("result", "TEXT", "NULL"),
    ("reason", "TEXT", "NULL"),
    ("notes", "TEXT", "NULL"),
    ("created_at", "TEXT", "CURRENT_TIMESTAMP"),
    # P3-Bug: 暂停持久化支持（累计暂停秒数，刷新后可恢复）
    ("paused_seconds", "INTEGER", "0"),
)


def _ensure_table_columns(
    cur,
    table: str,
    columns: Sequence[Tuple[str, str, Optional[str]]],
) -> None:
    """幂等补列（仅在列缺失时 ADD COLUMN）。"""
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    for name, col_type, default in columns:
        if name in existing:
            continue
        try:
            if default is not None:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN {name} {col_type} DEFAULT {default}"
                )
            else:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")
        except sqlite3.OperationalError:
            pass


def ensure_schema(conn) -> None:
    """建立计时器域表（幂等，空库可成功）。"""
    cur = conn.cursor()
    cur.execute(TIMER_SESSIONS_DDL)
    _ensure_table_columns(cur, "timer_sessions", TIMER_SESSIONS_COLUMNS)
    conn.commit()


__all__ = [
    "TIMER_SESSIONS_COLUMNS",
    "TIMER_SESSIONS_DDL",
    "ensure_schema",
]
